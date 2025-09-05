import time
import pytest

from app import create_app, db, socketio
from app.models import User, ChatSession


@pytest.fixture
def app_instance():
    app = create_app()
    app.config['TESTING'] = True
    # Use a fast in-memory sqlite DB for tests
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_join_session_creates_chat_session(app_instance):
    app = app_instance

    # Force SocketIO to use the threading async mode for tests to avoid eventlet/gevent issues
    socketio.init_app(app, async_mode='threading')

    # Create a customer user and mark them logged in via the test client's session
    with app.app_context():
        user = User(
            username='testcust',
            email='cust@example.com',
            first_name='Test',
            last_name='Customer',
            is_admin=False,
            is_active=True,
        )
        user.set_password('x')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    flask_test_client = app.test_client()

    # Authenticate by setting the Flask-Login session keys directly
    with flask_test_client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

    # Instead of using the SocketIO test client (which can block in some
    # environments), call the session-creation helper synchronously.
    from app.chat.events import create_chat_session

    fake_sid = 'testsid'
    with app.app_context():
        # Call synchronously to create the session
        create_chat_session(app, fake_sid, user_id, 'Tester')

        session = ChatSession.query.order_by(ChatSession.created_at.desc()).first()
        assert session is not None
        assert session.status == 'waiting'
        assert session.customer_id == user_id
