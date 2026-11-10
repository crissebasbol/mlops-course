class PreprocessingError(Exception):
    """Error base del preprocesamiento."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": type(self).__name__, "field": self.field, "message": self.message}


class EmptyTextError(PreprocessingError):
    def __init__(self, field: str):
        super().__init__(field, f"{field} no puede estar vacío")


class NotNumericError(PreprocessingError):
    def __init__(self, field: str, value):
        self.value = value
        super().__init__(field, f"{field} debe ser numérico, llegó {value!r}")


class OutOfRangeError(PreprocessingError):
    def __init__(self, field: str, value: float, min_value: float, max_value: float):
        self.value = value
        self.min_value = min_value
        self.max_value = max_value
        super().__init__(field, f"{field} debe estar entre {min_value} y {max_value}, llegó {value}")
