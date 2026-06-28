from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange


class CurriculumForm(FlaskForm):
    """Covers every NUC-relevant field per spec §9: course title, course
    code, credit units, course description, learning outcomes, prerequisite
    courses, assessment breakdown, and recommended reading list.
    Course code/title/credit units live on the linked Course record;
    programme_id selects which course this proposal is creating/revising.
    """
    programme_id = SelectField("Programme", coerce=int, validators=[DataRequired()])
    course_code = StringField("Course Code", validators=[DataRequired(), Length(max=20)])
    course_title = StringField("Course Title", validators=[DataRequired(), Length(max=200)])
    credit_units = IntegerField("Credit Units", validators=[DataRequired(), NumberRange(min=1, max=10)])
    level = StringField("Level", validators=[Length(max=10)])
    semester = SelectField(
        "Semester",
        choices=[("First", "First"), ("Second", "Second")],
        validators=[DataRequired()],
    )

    course_description = TextAreaField("Course Description", validators=[DataRequired()])
    learning_outcomes = TextAreaField("Learning Outcomes", validators=[DataRequired()])
    prerequisites = TextAreaField("Prerequisite Courses")
    reading_list = TextAreaField("Recommended Reading List", validators=[DataRequired()])

    # Assessment breakdown is collected as two numeric fields in the UI
    # (CA / Exam) and assembled into the assessment_breakdown JSON field.
    ca_score = IntegerField("Continuous Assessment (%)", validators=[DataRequired(), NumberRange(min=0, max=100)])
    exam_score = IntegerField("Examination (%)", validators=[DataRequired(), NumberRange(min=0, max=100)])

    submit = SubmitField("Save Draft")
