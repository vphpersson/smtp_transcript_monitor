from option_parser import OptionParser
from ecs_tools_py import make_log_action

from smtp_transcript_monitor import LOG


class SMTPTranscriptOptionParser(OptionParser):
    class Namespace:
        transcript_directory: str | None
        sleep_time: float

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            **(
                dict(description='Monitor a directory for SMTP transcripts.') | kwargs
            )
        )

        self.add_argument(
            '--transcript-directory',
            default='.',
            help='The path of a directory from which to read transcripts.'
        )

        self.add_argument(
            '--log',
            help='A log specifier specifying how logging is to be performed.',
            action=make_log_action(event_provider='smtp_transcript_monitor', log=LOG)
        )

        self.add_argument(
            '--sleep-time',
            help='The number of seconds to sleep before checking the transcript directory.',
            type=float,
            default=30.0
        )
