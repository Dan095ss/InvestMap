from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint
from .extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)  # user | moderator | admin
    avatar = db.Column(db.String(255))
    # Тип профиля: physical (физ.лицо) | investor (юрлицо/инвестор)
    profile_type = db.Column(db.String(20), default="physical", nullable=False)
    company_name = db.Column(db.String(200))  # для инвесторов
    inn = db.Column(db.String(20))            # ИНН
    phone = db.Column(db.String(40))
    bio = db.Column(db.Text)                  # о себе / о компании
    email_notifications = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    comments = db.relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    subscriptions = db.relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    activities = db.relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    donations = db.relationship("Donation", back_populates="user", cascade="all, delete-orphan")
    votes = db.relationship("InitiativeVote", back_populates="user", cascade="all, delete-orphan")
    tickets = db.relationship("SupportTicket", back_populates="user", cascade="all, delete-orphan")
    interests = db.relationship("InvestorInterest", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_moderator(self):
        return self.role in ("moderator", "admin")

    @property
    def is_investor(self):
        return self.profile_type == "investor"


class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    short_description = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    goal = db.Column(db.Text)  # цель проекта

    type = db.Column(db.String(40), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, index=True)
    district = db.Column(db.String(60), nullable=False, index=True)

    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(255))

    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    budget = db.Column(db.BigInteger)  # ₽
    responsible = db.Column(db.String(200))  # ответственные: ведомство/компания
    cover = db.Column(db.String(255))  # путь к обложке

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    media = db.relationship("ProjectMedia", back_populates="project", cascade="all, delete-orphan")
    timeline = db.relationship(
        "TimelineEvent", back_populates="project", cascade="all, delete-orphan", order_by="TimelineEvent.date"
    )
    jobs = db.relationship("Job", back_populates="project", cascade="all, delete-orphan")
    comments = db.relationship(
        "Comment", back_populates="project", cascade="all, delete-orphan", order_by="Comment.created_at"
    )

    @property
    def open_jobs(self):
        return [j for j in self.jobs if j.is_open]


class ProjectMedia(db.Model):
    __tablename__ = "project_media"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    kind = db.Column(db.String(20), default="photo")  # photo | document
    url = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(255))

    project = db.relationship("Project", back_populates="media")


class TimelineEvent(db.Model):
    __tablename__ = "timeline_events"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="planned")  # done | in_progress | planned

    project = db.relationship("Project", back_populates="timeline")


class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    requirements = db.Column(db.Text)
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    is_open = db.Column(db.Boolean, default=True)
    contact = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project", back_populates="jobs")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_moderator = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project", back_populates="comments")
    user = db.relationship("User", back_populates="comments")


class Initiative(db.Model):
    __tablename__ = "initiatives"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    short_description = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    author_type = db.Column(db.String(40), default="municipality")  # municipality | ngo | citizen
    author_name = db.Column(db.String(200))
    proposed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    district = db.Column(db.String(60), index=True)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    cover = db.Column(db.String(255))
    goal_amount = db.Column(db.BigInteger, default=0)
    collected_amount = db.Column(db.BigInteger, default=0)
    status = db.Column(db.String(40), default="active")  # active | funded | closed | moderation | rejected
    end_date = db.Column(db.Date)
    views = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    proposed_by = db.relationship("User", foreign_keys=[proposed_by_id])

    donations = db.relationship("Donation", back_populates="initiative", cascade="all, delete-orphan")
    votes = db.relationship("InitiativeVote", back_populates="initiative", cascade="all, delete-orphan")

    @property
    def progress_pct(self):
        if not self.goal_amount:
            return 0
        return min(100, round(self.collected_amount * 100 / self.goal_amount))

    @property
    def votes_count(self):
        return len(self.votes)


class Donation(db.Model):
    __tablename__ = "donations"
    id = db.Column(db.Integer, primary_key=True)
    initiative_id = db.Column(db.Integer, db.ForeignKey("initiatives.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    amount = db.Column(db.BigInteger, nullable=False)
    anonymous = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    initiative = db.relationship("Initiative", back_populates="donations")
    user = db.relationship("User", back_populates="donations")


class InitiativeVote(db.Model):
    __tablename__ = "initiative_votes"
    id = db.Column(db.Integer, primary_key=True)
    initiative_id = db.Column(db.Integer, db.ForeignKey("initiatives.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("initiative_id", "user_id", name="uq_vote_user_initiative"),)

    initiative = db.relationship("Initiative", back_populates="votes")
    user = db.relationship("User", back_populates="votes")


class Subscription(db.Model):
    __tablename__ = "subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    initiative_id = db.Column(db.Integer, db.ForeignKey("initiatives.id"), nullable=True)
    district = db.Column(db.String(60), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="subscriptions")
    project = db.relationship("Project")
    initiative = db.relationship("Initiative")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)
    link = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="notifications")


class Activity(db.Model):
    __tablename__ = "activities"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kind = db.Column(db.String(40), nullable=False)  # comment | vote | donation | subscription | ...
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="activities")


class SupportTicket(db.Model):
    __tablename__ = "support_tickets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    reply = db.Column(db.Text)
    status = db.Column(db.String(20), default="open")  # open | answered | closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    answered_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="tickets")


class InvestorInterest(db.Model):
    """Заявка инвестора на интерес к проекту."""
    __tablename__ = "investor_interests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    amount = db.Column(db.BigInteger)       # предполагаемый объём инвестиций, ₽
    message = db.Column(db.Text)
    contact = db.Column(db.String(200))     # доп. контакт
    status = db.Column(db.String(20), default="new")  # new | reviewed | accepted | declined
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="interests")
    project = db.relationship("Project")


def log_activity(user, kind, message, link=None):
    a = Activity(user_id=user.id, kind=kind, message=message, link=link)
    db.session.add(a)
    return a


def notify(user_id, title, body=None, link=None):
    n = Notification(user_id=user_id, title=title, body=body, link=link)
    db.session.add(n)
    # Параллельно шлём email (в dev — просто в лог). Импортируем лениво, чтобы избежать циклов.
    try:
        from .mailer import notify_by_email
        user = User.query.get(user_id)
        if user:
            notify_by_email(user, title, body, link)
    except Exception:
        # никогда не валим бизнес-логику из-за почты
        pass
    return n
