from flask import Blueprint

bp = Blueprint('messenger', __name__)

from app.chat import routes, events