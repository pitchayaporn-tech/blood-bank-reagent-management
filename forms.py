from flask_wtf import FlaskForm
from wtforms import DateField, DateTimeField, DecimalField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, InputRequired, Length, Optional, Regexp


ROLE_OPTIONS = [
    ("MT", "Medical Technologist"),
    ("SUP", "Laboratory Supervisor"),
    ("ADM", "System Administrator"),
]


def role_choices():
    return ROLE_OPTIONS


REAGENT_TYPE_OPTIONS = [
    ("Blood Grouping Reagent", "Blood Grouping Reagent"),
    ("AHG Reagent", "AHG Reagent"),
    ("Screening & Identification Cells", "Screening & Identification Cells"),
    ("Control Reagent", "Control Reagent"),
    ("Enhancement Reagent", "Enhancement Reagent"),
    ("Other", "Other"),
]


def reagent_type_choices(current_value=None):
    choices = [("", "Select Reagent Type"), *REAGENT_TYPE_OPTIONS]
    if current_value and current_value not in {value for value, _ in choices}:
        choices.append((current_value, current_value))
    return choices


class ReagentForm(FlaskForm):
    reagent_name = StringField("Reagent Name", validators=[DataRequired(), Length(max=150)])
    reagent_type = SelectField("Reagent Type", choices=reagent_type_choices(), validators=[DataRequired()])
    manufacturer = StringField("Manufacturer", validators=[Optional(), Length(max=150)])
    lot_number = StringField("Lot Number", validators=[Optional(), Length(max=100)])
    manufacturer_date = DateField("Manufacturer Date", format="%Y-%m-%d", validators=[Optional()])
    expiry_date = DateField("Expiry Date", format="%Y-%m-%d", validators=[Optional()])
    storage_condition = StringField("Storage Condition", validators=[Optional(), Length(max=150)])
    supplier = StringField("Supplier", validators=[DataRequired(), Length(max=150)])


class DeleteForm(FlaskForm):
    pass


class SupplierForm(FlaskForm):
    supplier_name = StringField("Supplier Name", validators=[DataRequired(), Length(max=150)])
    contact = StringField("Contact", validators=[Optional(), Length(max=150)])


class InventoryForm(FlaskForm):
    quantity = DecimalField("Quantity", validators=[InputRequired()], places=2)
    minimum_stock = DecimalField("Minimum Stock", validators=[InputRequired()], places=2)
    storage_location = StringField("Storage Location", validators=[Optional(), Length(max=150)])
    status = StringField("Status", validators=[DataRequired(), Length(max=50)])


class ReceivingForm(FlaskForm):
    receiving_date = DateField("Receiving Date", format="%Y-%m-%d", validators=[DataRequired()])
    reagent_id = SelectField("Reagent", coerce=int, validators=[DataRequired()])
    lot_number = StringField("Lot Number", validators=[DataRequired(), Length(max=100)])
    expiry_date = DateField("Expiry Date", format="%Y-%m-%d", validators=[DataRequired()])
    quantity_received = DecimalField("Quantity Received", validators=[DataRequired()], places=2)


class QCRecordForm(FlaskForm):
    qc_datetime = DateTimeField(
        "QC Date and Time",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
    )
    qc_type = SelectField(
        "QC Type",
        choices=[
            ("Daily QC", "Daily QC"),
            ("New Lot QC", "New Lot QC"),
            ("New Vial QC", "New Vial QC"),
            ("Periodic QC", "Periodic QC"),
        ],
        validators=[DataRequired()],
    )
    qc_result = SelectField(
        "QC Result",
        choices=[
            ("", "Select QC Result"),
            ("Pass", "Pass"),
            ("Fail", "Fail"),
        ],
        validators=[DataRequired()],
    )
    qc_comment = StringField("QC Comment", validators=[Optional(), Length(max=255)])
    inventory_id = SelectField("Lot", coerce=int, validators=[DataRequired()])


class ReagentRequestForm(FlaskForm):
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=255)])


class ReagentRequestStatusForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[
            ("Pending", "Pending"),
            ("Approved", "Approved"),
            ("Rejected", "Rejected"),
            ("Completed", "Completed"),
        ],
        validators=[DataRequired()],
    )


class RegistrationForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=150)])
    email = StringField(
        "Email",
        validators=[
            Optional(),
            Length(max=255),
            Regexp(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", message="Enter a valid email address."),
        ],
    )
    role = SelectField("Role", choices=role_choices(), validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
