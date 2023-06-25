from option_parser import OptionParser


class SMTPTranscriptOptionParser(OptionParser):
    class Namespace:
        transcript_directory: str | None
        log_path: str | None
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
            '--log-path',
            help='The path where to store logs.'
        )

        self.add_argument(
            '--sleep-time',
            help='The number of seconds to sleep before checking the transcript directory.',
            type=float,
            default=30.0
        )
