from pydantic import AnyHttpUrl, BaseModel


class Settings(BaseModel):
    login_url: AnyHttpUrl = AnyHttpUrl("http://frontend.local/login")
    activation_base_url: AnyHttpUrl = AnyHttpUrl(
        "http://frontend.local/activate"
    )
    password_reset_base_url: AnyHttpUrl = AnyHttpUrl(
        "http://frontend.local/password-reset"
    )
    email_change_base_url: AnyHttpUrl = AnyHttpUrl(
        "http://frontend.local/email-change"
    )
