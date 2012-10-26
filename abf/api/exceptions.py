

class AbfApiException(Exception):
    pass


class PageNotFoundError(AbfApiException):
    pass


class AuthError(AbfApiException):
    pass

class ForbiddenError(AbfApiException):
    pass

class RateLimitError(AbfApiException):
    pass

class InternalServerError(AbfApiException):
    pass

class ServerWorksError(AbfApiException):
    pass

class BadRequestError(AbfApiException):
    pass
    