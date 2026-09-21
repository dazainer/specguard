class EvaluationStopped(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)
