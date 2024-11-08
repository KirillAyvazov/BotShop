from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, PrimaryKeyConstraint


Base = declarative_base()
db = SQLAlchemy(model_class=Base)


class User(Base):
    __tablename__ = "user"

    tgId = Column(Integer)
    firstName = Column(String)
    lastName = Column(String)
    nickname = Column(String)
    phoneNumber = Column(String)
    homeAddress = Column(String)

    __table_args__ = (
        PrimaryKeyConstraint('tgId'),
    )
