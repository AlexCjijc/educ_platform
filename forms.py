from wtforms import Form, StringField, PasswordField, validators

class RegisterForm(Form):
    name = StringField("Имя", [validators.Length(min=2, max=128)])
    email = StringField("Email", [validators.Email()])
    password = PasswordField("Пароль", [validators.Length(min=6, max=128)])

class LoginForm(Form):
    email = StringField("Email", [validators.Email()])
    password = PasswordField("Пароль", [validators.DataRequired()])
