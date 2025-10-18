from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, FloatField, SelectField, HiddenField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, NumberRange, Optional

# User Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    # Add other user fields if needed in registration
    submit = SubmitField('Register')

# Admin Forms
class ParkingLotForm(FlaskForm):
    prime_location_name = StringField('Location Name', validators=[DataRequired(), Length(max=100)])
    price = FloatField('Price (per hour)', validators=[DataRequired(), NumberRange(min=0)])
    address = StringField('Address', validators=[DataRequired(), Length(max=200)])
    pin_code = StringField('Pin Code', validators=[DataRequired(), Length(min=5, max=10)])
    maximum_number_of_spots = IntegerField('Maximum Spots', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Save Parking Lot')

# User Action Forms (Potentially simplified as per requirements)
class SelectLotForm(FlaskForm):
    # Users choose a lot, not a spot
    parking_lot = SelectField('Choose Parking Lot', coerce=int, validators=[DataRequired()])
    submit_book = SubmitField('Book First Available Spot')

class ReleaseSpotForm(FlaskForm):
    # Hidden field might carry reservation ID or spot ID
    reservation_id = HiddenField()
    submit_release = SubmitField('Release My Spot')