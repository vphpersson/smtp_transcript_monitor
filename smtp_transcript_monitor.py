#!/usr/bin/env python

from asyncio import run as asyncio_run
from pathlib import Path
from logging import INFO

from smtp_transcript_monitor import LOG, log_monitor
from smtp_transcript_monitor.cli import SMTPTranscriptOptionParser


async def main():
    try:
        args: SMTPTranscriptOptionParser.Namespace = SMTPTranscriptOptionParser().parse_options(
            read_config_options=dict(raise_exception=False)
        )
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
