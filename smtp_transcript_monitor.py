#!/usr/bin/env python

from asyncio import run as asyncio_run
from pathlib import Path
from logging import INFO, StreamHandler
from logging.handlers import TimedRotatingFileHandler

from ecs_tools_py import make_log_handler

from smtp_transcript_monitor import LOG, log_monitor
from smtp_transcript_monitor.cli import SMTPTranscriptOptionParser


async def main():
    try:
        args: SMTPTranscriptOptionParser.Namespace = SMTPTranscriptOptionParser().parse_options(
            read_config_options=dict(raise_exception=False)
        )

        log_handler_args = dict(
            provider_name='smtp_transcript_monitor',
            generate_field_names=('event.timezone', 'host.name', 'host.hostname')
        )
        if args.log_path:
            log_handler = make_log_handler(
                base_class=TimedRotatingFileHandler,
                **log_handler_args
            )(filename=args.log_path, when='D')
        else:
            log_handler = make_log_handler(
                base_class=StreamHandler,
                **log_handler_args
            )()

        LOG.addHandler(hdlr=log_handler)
        LOG.setLevel(level=INFO)

        await log_monitor(
            transcript_directory=Path(args.transcript_directory),
            sleep_duration=args.sleep_time
        )
    except KeyboardInterrupt:
        pass
    except Exception:
        LOG.exception(msg='An unexpected error occurred.')


if __name__ == '__main__':
    asyncio_run(main())
