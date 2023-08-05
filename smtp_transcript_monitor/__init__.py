from logging import getLogger, Logger
from asyncio import sleep as asyncio_sleep
from typing import NoReturn, Final
from re import compile as re_compile, Pattern as RePattern, IGNORECASE as RE_IGNORECASE
from pathlib import Path
from os import stat_result
from datetime import datetime
from subprocess import run as subprocess_run, PIPE as SUBPROCESS_PIPE

from ecs_py import Base, User
from ecs_tools_py import user_from_smtp_to_from
from smtp_lib.parse.transcript import parse_transcript, ExtraExchangeData, SMTPExchange

LOG: Final[Logger] = getLogger(__name__)


_MAIL_FROM_PATTERN: Final[RePattern] = re_compile(pattern=r'^FROM:<([^>]+)>.*$', flags=RE_IGNORECASE)
_RCPT_TO_PATTERN: Final[RePattern] = re_compile(pattern=r'^TO:<([^>]+)>.*$', flags=RE_IGNORECASE)
_BIRTH_PATTERN: Final[RePattern] = re_compile(
    pattern=r'^\s*Birth: (.+)... ([^ ]+)$'
)


def get_creation_time(file_path: str) -> datetime:
    stat_process = subprocess_run(
        ['stat', file_path],
        stdout=SUBPROCESS_PIPE,
        text=True
    )
    return next(
        datetime.strptime(
            f'{match.group(1)} {match.group(2)}',
            '%Y-%m-%d %H:%M:%S.%f %z'
        )
        for line in stat_process.stdout.splitlines() if (match := _BIRTH_PATTERN.search(string=line))
    )


async def log_monitor(transcript_directory: Path, sleep_duration: float = 30.0) -> NoReturn:
    while True:
        transcript_file: Path
        for transcript_file in transcript_directory.glob(pattern='*_*_*_*'):
            try:
                if not transcript_file.is_file():
                    continue

                transcript_file_stat_result: stat_result = transcript_file.stat(follow_symlinks=False)
                last_modified: datetime = datetime.fromtimestamp(transcript_file_stat_result.st_mtime).astimezone()

                time_difference_seconds: int = (datetime.now().astimezone() - last_modified).seconds

                if not (time_difference_seconds >= int(sleep_duration)):
                    continue

                server_address, server_port, client_address, client_port = transcript_file.name.split('_')

                transcript_data: str = transcript_file.read_text()

                exchange: list[SMTPExchange]
                extra_exchange_data: ExtraExchangeData | None
                exchange, extra_exchange_data = parse_transcript(transcript_data=transcript_data)

                base = Base()
                base.assign(
                    value_dict={
                        'client.address': client_address,
                        'client.port': client_port,
                        'event.start': get_creation_time(file_path=str(transcript_file)),
                        'event.end': last_modified,
                        'server.address': server_address,
                        'server.port': int(server_port),
                        'smtp.ehlo': next(
                            (
                                entry.request.arguments_string
                                for entry in exchange
                                if entry.request and entry.request.command.upper() == 'EHLO'
                            ),
                            None
                        ),
                        'smtp.mail_from': next(
                            (
                                pattern_match.group(1)
                                for entry in exchange
                                if (
                                    entry.request
                                    and entry.request.command.upper() == 'MAIL'
                                    and entry.request.arguments_string.upper().startswith('FROM:')
                                ) and (pattern_match := _MAIL_FROM_PATTERN.match(string=entry.request.arguments_string))
                            ),
                            None
                        ),
                        'smtp.rcpt_to': next(
                            (
                                pattern_match.group(1)
                                for entry in exchange
                                if (
                                    entry.request
                                    and entry.request.command.upper() == 'RCPT'
                                    and entry.request.arguments_string.upper().startswith('TO:')
                                ) and (pattern_match := _RCPT_TO_PATTERN.match(string=entry.request.arguments_string))
                            ),
                            None
                        ),
                        'smtp.transcript.exchange': exchange,
                        'smtp.transcript.original': transcript_data,
                        'network.protocol': 'smtp',
                        'network.transport': 'tcp',
                    }
                )

                if error_message := extra_exchange_data.error_message:
                    base.set_field_value(field_name='error.message', value=error_message)

                if error_code := extra_exchange_data.error_code:
                    base.set_field_value(field_name='error.code', value=error_code)

                if error_type := extra_exchange_data.error_type:
                    base.set_field_value(field_name='error.type', value=error_type)

                related_users: set[str] = set()
                related_hosts: set[str] = set()

                if base.smtp:
                    user: User = user_from_smtp_to_from(ecs_smtp=base.smtp)
                    base.user = user

                    if user_email := user.email:
                        user_email_name, user_email_domain = user_email.split(sep='@', maxsplit=1)
                        related_users.add(user_email_name.lower())
                        related_hosts.add(user_email_domain.lower())

                    if user.target and (user_target_email := user.target.email):
                        user_target_email_name, user_target_email_domain = user_target_email.split(sep='@', maxsplit=1)
                        related_users.add(user_target_email_name.lower())
                        related_hosts.add(user_target_email_domain.lower())

                if ehlo := base.get_field_value(field_name='smtp.ehlo'):
                    related_hosts.add(ehlo)

                base.assign(
                    value_dict={
                        'related.user': list(related_users) or None,
                        'related.hosts': list(related_hosts) or None
                    }
                )

                LOG.info(
                    msg='An SMTP transcript was parsed.',
                    extra=dict(base) | dict(_ecs_logger_handler_options=dict(merge_extra=True))
                )

                transcript_file.unlink()
            except:
                LOG.exception(
                    msg='An unexpected error occurred when attempting to handle a file.'
                )

        await asyncio_sleep(delay=sleep_duration)
