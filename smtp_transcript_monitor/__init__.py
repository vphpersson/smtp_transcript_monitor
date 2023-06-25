from logging import getLogger, Logger
from asyncio import sleep as asyncio_sleep
from typing import NoReturn, Final
from re import compile as re_compile, Pattern as RePattern, IGNORECASE as RE_IGNORECASE
from pathlib import Path
from os import stat_result
from datetime import datetime

from ecs_py import Base, SMTP, SMTPTranscript, Client, Server, Network, Error
from smtp_lib.parse.transcript import parse_transcript, ExtraExchangeData, SMTPExchange

LOG: Final[Logger] = getLogger(__name__)


_MAIL_FROM_PATTERN: Final[RePattern] = re_compile(pattern=r'^FROM:<([^>]+)>.*$', flags=RE_IGNORECASE)
_RCPT_TO_PATTERN: Final[RePattern] = re_compile(pattern=r'^TO:<([^>]+)>.*$', flags=RE_IGNORECASE)


async def log_monitor(transcript_directory: Path, sleep_duration: float = 30.0) -> NoReturn:
    while True:
        await asyncio_sleep(delay=sleep_duration)

        transcript_file: Path
        for transcript_file in transcript_directory.glob(pattern='*'):
            try:
                if not transcript_file.is_file():
                    continue

                transcript_file_stat_result: stat_result = transcript_file.stat(follow_symlinks=False)

                time_difference_seconds: int = (
                        datetime.now().astimezone()
                        - datetime.fromtimestamp(transcript_file_stat_result.st_mtime).astimezone()
                ).seconds

                if not (time_difference_seconds >= int(sleep_duration)):
                    continue

                server_address, server_port, client_address, client_port = transcript_file.name.split('_')

                base = Base(
                    client=Client(
                        address=client_address,
                        port=int(client_port)
                    ),
                    error=Error(),
                    server=Server(
                        address=server_address,
                        port=int(server_port)
                    ),
                    network=Network(
                        protocol='smtp',
                        transport='tcp'
                    ),
                    smtp=SMTP()
                )

                transcript_data: str = transcript_file.read_text()

                base.smtp.transcript = SMTPTranscript(original=transcript_data)

                exchange: list[SMTPExchange]
                extra_exchange_data: ExtraExchangeData | None
                exchange, extra_exchange_data = parse_transcript(transcript_data=transcript_data)

                base.smtp.transcript.exchange = exchange

                base.smtp.ehlo = next(
                    (
                        entry.request.arguments_string
                        for entry in exchange
                        if entry.request and entry.request.command.upper() == 'EHLO'
                    ),
                    None
                )

                base.smtp.mail_from = next(
                    (
                        _MAIL_FROM_PATTERN.match(string=entry.request.arguments_string).group(1)
                        for entry in exchange
                        if (
                            entry.request
                            and entry.request.command.upper() == 'MAIL'
                            and entry.request.arguments_string.upper().startswith('FROM:')
                        )
                    ),
                    None
                )

                base.smtp.rcpt_to = next(
                    (
                        _RCPT_TO_PATTERN.match(string=entry.request.arguments_string).group(1)
                        for entry in exchange
                        if (
                            entry.request
                            and entry.request.command.upper() == 'RCPT'
                            and entry.request.arguments_string.upper().startswith('TO:')
                        )
                    ),
                    None
                )

                if error_message := extra_exchange_data.error_message:
                    base.error.message = error_message

                if error_code := extra_exchange_data.error_code:
                    base.error.code = error_code

                if error_type := extra_exchange_data.error_type:
                    base.error.type = error_type

                LOG.info(
                    msg='SMTP traffic was observed.',
                    extra=dict(base) | dict(_ecs_logger_handler_options=dict(merge_extra=True))
                )
            except:
                LOG.exception(
                    msg='An unexpected error occurred when attempting to parse a file.'
                )
