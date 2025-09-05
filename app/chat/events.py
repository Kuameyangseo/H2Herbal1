from flask import request, current_app
from flask_login import current_user
from app import socketio, db
from app.models import ChatSession, ChatMessage, User
from datetime import datetime
from flask_socketio import join_room, leave_room


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f'Client connected: {request.sid}')
    # If this socket belongs to an authenticated admin user, add them to the
    # global admins room so server-side emits to room='admins' reach them.
    try:
        if current_user.is_authenticated and getattr(current_user, 'is_admin', False):
            join_room('admins')
            current_app.logger.info(f"Socket {request.sid} joined admins room for user {current_user.id}")
    except Exception:
        # Don't break connection handling if anything goes wrong here
        current_app.logger.exception('Failed to auto-join admin to admins room on connect')


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnect"""
    print(f'Client disconnected: {request.sid}')


@socketio.on('join_room')
def handle_join_room(data):
    """Handle joining a room"""
    # Handle case where data might be a string or dict
    if isinstance(data, str):
        room = data
    else:
        room = data.get('room')

    if room:
        join_room(room)
        print(f'Client {request.sid} joined room: {room}')


@socketio.on('join_session')
def handle_join_session(data):
    """Handle joining a chat session"""
    session_id = data.get('session_id')
    customer_name = data.get('customer_name', 'Customer')
    # Allow clients to join silently (no admin join notifications)
    silent = data.get('silent', False)

    if session_id:
        # Join the session room for the requested session id (best-effort)
        join_room(f'session_{session_id}')
        print(f'Client {request.sid} joined session: {session_id}')

        # Lookup existing session
        session = ChatSession.query.get(session_id)

        # If session does not exist, create it and ensure the client joins the correct room using the created id
        if not session:
            session = ChatSession(
                customer_id=(current_user.id if current_user.is_authenticated and not current_user.is_admin else None),
                subject='Customer Support',
                priority='normal',
                status='waiting'
            )
            db.session.add(session)
            db.session.commit()

            # Re-join the room for the created session id
            try:
                leave_room(f'session_{session_id}')
            except Exception:
                pass
            join_room(f'session_{session.id}')

            # Emit event to admins about new session
            socketio.emit('new_chat_session', {
                'session_id': session.id,
                'customer_name': customer_name,
                'message_preview': 'New chat session started'
            }, room='admins')

            # Emit system message to the correct session room so customer sees session start
            socketio.emit('message_sent', {
                'session_id': session.id,
                'message': 'Chat session started',
                'sender_type': 'system',
                'created_at': session.created_at.isoformat() if session.created_at else None
            }, room=f'session_{session.id}')

        # If an admin joined an existing session, notify the session participants (unless silent)
        elif current_user.is_authenticated and current_user.is_admin:
            if not silent and session and getattr(session, 'status', None) != 'closed':
                try:
                    socketio.emit('admin_notification', {
                        'title': 'Admin Joined Session',
                        'message': f"Admin {current_user.first_name} {current_user.last_name} joined the chat session",
                        'session_id': session.id
                    }, room=f'session_{session.id}')
                except Exception:
                    pass
                

@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a message"""
    session_id = data.get('session_id')
    message_text = data.get('message', '').strip()
    
    if session_id and message_text:
        # Check if session exists and get its current status
        session = ChatSession.query.get(session_id)
        if not session:
            return
        
        # If this is a customer message to a closed session, reopen it to 'waiting' status
        is_customer_message = not (current_user.is_authenticated and current_user.is_admin)
        if is_customer_message and session.status == 'closed':
            session.status = 'waiting'
            session.closed_at = None
            session.agent_id = None  # Unassign the agent so it can be reassigned
            db.session.commit()
            
            # Emit session status update to admins
            socketio.emit('session_updated', {
                'session_id': session_id,
                'status': 'waiting',
                'agent_id': None,
                'agent_name': 'Unassigned',
                'message': 'Session reopened - customer sent new message'
            }, room='admins')
            
            # Also emit to the session room
            socketio.emit('session_updated', {
                'session_id': session_id,
                'status': 'waiting',
                'agent_id': None,
                'agent_name': 'Unassigned',
                'message': 'Session reopened - customer sent new message'
            }, room=f'session_{session_id}')
        
        # If this is an admin socket message, ensure the admin is assigned to this session
        if current_user.is_authenticated and current_user.is_admin:
            if session.agent_id is None or session.agent_id != current_user.id:
                # Do not allow unassigned admins to send messages via socket
                return

        # Create message in database
        message = ChatMessage(
            session_id=session_id,
            sender_id=current_user.id if current_user.is_authenticated else None,
            message=message_text,
            message_type='text'
        )
        db.session.add(message)
        db.session.commit()
        
        # Prepare message data for response
        message_data = {
            'id': message.id,
            'session_id': message.session_id,
            'sender_id': message.sender_id,
            'sender_name': f"{current_user.first_name} {current_user.last_name}" if current_user.is_authenticated else 'Customer',
            'sender_type': 'agent' if current_user.is_authenticated and current_user.is_admin else 'customer',
            'message': message.message,
            'message_type': message.message_type,
            'attachment_url': message.attachment_url,
            'is_read': message.is_read,
            'created_at': message.created_at.isoformat() if message.created_at else None
        }
        
        # Emit event to session room (this will reach both customer and admin)
        socketio.emit('message_sent', message_data, room=f'session_{session_id}')

        # Also emit message to admins so admin dashboards receive the first-message
        # immediately and can create a lightweight session entry if needed.
        try:
            socketio.emit('message_sent', message_data, room='admins')
        except Exception:
            pass
        
        # Also emit to admins room for notifications
        # Only send notification if this is a customer message (not admin messages to avoid loops)
        # and only send a simple notification, not the full message content
        if not (current_user.is_authenticated and current_user.is_admin):
            socketio.emit('admin_notification', {
                'title': 'New Message',
                'message': f"New message from {message_data['sender_name']}",
                'session_id': session_id
            }, room='admins')

@socketio.on('typing')
def handle_typing(data):
    """Handle typing indicator"""
    session_id = data.get('session_id')
    is_typing = data.get('is_typing', False)
    
    if session_id:
        # Emit typing status to session room
        typing_data = {
            'session_id': session_id,
            'is_typing': is_typing,
            'user_id': current_user.id if current_user.is_authenticated else None
        }
        
        # Send to customer if admin is typing, or to admin if customer is typing
        if current_user.is_authenticated and current_user.is_admin:
            socketio.emit('agent_typing', typing_data, room=f'session_{session_id}')
        else:
            socketio.emit('user_typing', typing_data, room=f'session_{session_id}')

@socketio.on('close_session')
def handle_close_session(data):
    """Handle session closure"""
    session_id = data.get('session_id')
    
    if session_id:
        # Update session status to closed
        session = ChatSession.query.get(session_id)
        if session:
            from datetime import datetime
            session.status = 'closed'
            session.closed_at = datetime.utcnow()
            db.session.commit()
            
            # Create a persistent system message to notify participants of closure
            try:
                system_message = ChatMessage(
                    session_id=session_id,
                    sender_id=current_user.id if current_user.is_authenticated else None,
                    message='This chat session has been closed by support',
                    message_type='system'
                )
                db.session.add(system_message)
                db.session.commit()

                system_message_data = {
                    'id': system_message.id,
                    'session_id': system_message.session_id,
                    'sender_id': system_message.sender_id,
                    'sender_name': f"{current_user.first_name} {current_user.last_name}" if current_user.is_authenticated else 'System',
                    'sender_type': 'system',
                    'message': system_message.message,
                    'message_type': system_message.message_type,
                    'attachment_url': system_message.attachment_url,
                    'is_read': system_message.is_read,
                    'created_at': system_message.created_at.isoformat() if system_message.created_at else None
                }

                # Emit message_sent so participants see the closure message in chat history
                socketio.emit('message_sent', system_message_data, room=f'session_{session_id}')
            except Exception as e:
                # If message creation fails, still emit a closure event
                print('Failed to persist system closure message:', e)

            # Emit session closed event to session room and admins
            socketio.emit('session_closed', {
                'session_id': session_id,
                'message': 'This chat session has been closed'
            }, room=f'session_{session_id}')
            
            socketio.emit('session_closed', {
                'session_id': session_id,
                'message': 'This chat session has been closed'
            }, room='admins')

@socketio.on('delete_session')
def handle_delete_session(data):
    """Handle session deletion"""
    session_id = data.get('session_id')
    
    if session_id:
        # Delete all messages in the session
        ChatMessage.query.filter_by(session_id=session_id).delete()
        
        # Delete the session
        session = ChatSession.query.get(session_id)
        if session:
            db.session.delete(session)
            db.session.commit()
        
        # Emit session deleted event to admins
        socketio.emit('session_deleted', {
            'session_id': session_id
        }, room='admins')
        # Also notify the session room to clear any persisted customer widget state
        try:
            socketio.emit('clear_customer_session', {'session_id': session_id}, room=f'session_{session_id}')
        except Exception:
            pass


@socketio.on('clear_customer_session')
def handle_clear_customer_session(data):
    """Admin or server requests to clear a customer's persisted chat widget state.
    This handler rebroadcasts the clear command to the target session room so
    connected customers receive it regardless of whether the request originated
    via the REST API or an admin socket emit."""
    session_id = None
    try:
        session_id = data.get('session_id')
    except Exception:
        # data may be a plain value
        session_id = data

    if session_id:
        try:
            socketio.emit('clear_customer_session', {'session_id': session_id}, room=f'session_{session_id}')
        except Exception:
            pass