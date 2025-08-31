from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db, socketio
from app.chat import bp
from app.models import ChatSession, ChatMessage, User, CannedResponse, ChatAnalytics, Order
from app.models import ChatNotification
from datetime import datetime
import os
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

@bp.route('/chat')
@login_required
def customer_chat():
    """Customer chat interface"""
    # Get user's active sessions
    active_sessions = ChatSession.query.filter_by(
        customer_id=current_user.id,
        status='active'
    ).all()
    
    return render_template('messenger/customer_chat.html',
                         active_sessions=active_sessions)

@bp.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard interface"""
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('main.index'))
    
    # Get all active sessions
    active_sessions = ChatSession.query.filter_by(status='active').all()
    waiting_sessions = ChatSession.query.filter_by(status='waiting').all()
    
    return render_template('messenger/admin/dashboard.html',
                         active_sessions=active_sessions,
                         waiting_sessions=waiting_sessions)

# API Routes

@bp.route('/api/agents', methods=['GET'])
@login_required
def api_get_agents():
    """Get all available agents"""
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Get all admin users (agents)
        agents = User.query.filter_by(is_admin=True).all()
        
        # Convert to dictionary format
        agents_data = []
        for agent in agents:
            agent_data = {
                'id': agent.id,
                'username': agent.username,
                'email': agent.email,
                'first_name': agent.first_name,
                'last_name': agent.last_name,
                'is_online': False,  # In a real implementation, this would check actual online status
                'current_chats': 0   # In a real implementation, this would count current chats
            }
            agents_data.append(agent_data)
        
        return jsonify({
            'success': True,
            'agents': agents_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting agents: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to get agents'
        }), 500

@bp.route('/api/sessions', methods=['GET'])
@login_required
def api_get_sessions():
    """Get chat sessions for current user"""
    try:
        # Build query
        query = ChatSession.query
        
        # Filter by user
        if current_user.is_admin:
            # Admins can see all sessions
            pass
        else:
            # Customers see their own sessions
            query = query.filter_by(customer_id=current_user.id)
        
        # Order by creation date
        sessions = query.order_by(ChatSession.created_at.desc()).all()
        
        # Convert to dictionary format
        sessions_data = []
        for session in sessions:
            # Get the last message for this session
            last_message = ChatMessage.query.filter_by(session_id=session.id)\
                .order_by(ChatMessage.created_at.desc()).first()

            # Build customer object (if available)
            customer_obj = None
            recent_orders = []
            if session.customer:
                cust = session.customer
                customer_obj = {
                    'id': cust.id,
                    'first_name': cust.first_name,
                    'last_name': cust.last_name,
                    'email': cust.email,
                    'created_at': cust.created_at.isoformat() if cust.created_at else None,
                    'profile_image': getattr(cust, 'profile_image', None)
                }

                # Fetch last 5 orders for this customer to show in context panel
                try:
                    orders = Order.query.filter_by(user_id=cust.id).order_by(Order.created_at.desc()).limit(5).all()
                    for order in orders:
                        recent_orders.append({
                            'order_number': order.order_number,
                            'payment_status': order.payment_status,
                            'total_amount': float(order.total_amount) if order.total_amount is not None else 0.0,
                            'created_at': order.created_at.isoformat() if order.created_at else None
                        })
                except Exception:
                    recent_orders = []

            session_data = {
                'id': session.id,
                'customer_id': session.customer_id,
                'customer_name': f"{session.customer.first_name} {session.customer.last_name}" if session.customer else "Unknown",
                'customer': customer_obj,
                'recent_orders': recent_orders,
                'agent_id': session.agent_id,
                'agent_name': f"{session.agent.first_name} {session.agent.last_name}" if session.agent else "Unassigned",
                'status': session.status,
                'subject': session.subject,
                'priority': session.priority,
                'created_at': session.created_at.isoformat() if session.created_at else None,
                'updated_at': session.updated_at.isoformat() if session.updated_at else None,
                'closed_at': session.closed_at.isoformat() if session.closed_at else None,
                'last_message': last_message.message if last_message else "",
                'last_message_time': last_message.created_at.isoformat() if last_message else None
            }
            sessions_data.append(session_data)
        
        return jsonify({
            'success': True,
            'sessions': sessions_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting sessions: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to get sessions'
        }), 500

@bp.route('/api/sessions', methods=['POST'])
@login_required
def api_create_session():
    """Create a new chat session"""
    try:
        # Get request data
        data = request.get_json()
        subject = data.get('subject', 'General Inquiry')
        priority = data.get('priority', 'normal')
        
        # Validate priority
        if priority not in ['low', 'normal', 'high', 'urgent']:
            priority = 'normal'
        
        # Create session
        session = ChatSession(
            customer_id=current_user.id,
            subject=subject,
            priority=priority,
            status='waiting'  # Start in waiting status until admin assigns
        )
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Chat session created successfully',
            'session': {
                'id': session.id,
                'status': session.status,
                'created_at': session.created_at.isoformat() if session.created_at else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating session: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to create chat session'
        }), 500

@bp.route('/api/session', methods=['GET'])
def api_get_session():
    """Get or create a chat session for the current user"""
    try:
        if current_user.is_authenticated:
            # Try to find an existing active session for the user
            session = ChatSession.query.filter_by(
                customer_id=current_user.id,
                status='active'
            ).first()
            
            # If no active session, look for a waiting session
            if not session:
                session = ChatSession.query.filter_by(
                    customer_id=current_user.id,
                    status='waiting'
                ).first()
            
            # If no active or waiting session, look for a closed session
            if not session:
                session = ChatSession.query.filter_by(
                    customer_id=current_user.id,
                    status='closed'
                ).first()

                # If we found a closed session, reopen it as 'waiting' so an admin must assign it
                if session:
                    session.status = 'waiting'
                    session.closed_at = None
                    # Unassign any previous agent so admins must explicitly assign
                    session.agent_id = None
                    db.session.commit()

                    # Notify admins / session room that the session is now waiting for assignment
                    try:
                        socketio.emit('session_updated', {
                            'session_id': session.id,
                            'status': 'waiting',
                            'agent_id': None,
                            'agent_name': 'Unassigned',
                            'message': 'Customer reopened the chat and session is waiting for assignment'
                        }, room='admins')
                        socketio.emit('session_updated', {
                            'session_id': session.id,
                            'status': 'waiting',
                            'agent_id': None,
                            'agent_name': 'Unassigned',
                            'message': 'Customer reopened the chat and session is waiting for assignment'
                        }, room=f'session_{session.id}')
                    except Exception:
                        # Don't block the API if socket emit fails
                        pass
            
            # If no existing session, create a new one
            if not session:
                session = ChatSession(
                    customer_id=current_user.id,
                    subject='General Inquiry',
                    priority='normal',
                    status='waiting'  # Start in waiting status until admin assigns
                )
                db.session.add(session)
                db.session.commit()
                # Notify admins of the newly created session so they see it immediately
                try:
                    socketio.emit('new_chat_session', {
                        'session_id': session.id,
                        'customer_name': session.customer.first_name + ' ' + session.customer.last_name if session.customer else 'Customer',
                        'message_preview': ''
                    }, room='admins')
                except Exception:
                    pass
        else:
            # For anonymous users, create a new session
            session = ChatSession(
                subject='General Inquiry',
                priority='normal',
                status='waiting'  # Start in waiting status until admin assigns
            )
            db.session.add(session)
            db.session.commit()
            # Notify admins of the newly created anonymous session so it appears without refresh
            try:
                socketio.emit('new_chat_session', {
                    'session_id': session.id,
                    'customer_name': 'Customer',
                    'message_preview': ''
                }, room='admins')
            except Exception:
                pass
        
        # Prepare session data
        session_data = {
            'id': session.id,
            'customer_id': session.customer_id,
            'customer_name': f"{session.customer.first_name} {session.customer.last_name}" if session.customer else "Customer",
            'agent_id': session.agent_id,
            'agent_name': f"{session.agent.first_name} {session.agent.last_name}" if session.agent else "Unassigned",
            'status': session.status,
            'subject': session.subject,
            'priority': session.priority,
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'updated_at': session.updated_at.isoformat() if session.updated_at else None,
            'closed_at': session.closed_at.isoformat() if session.closed_at else None
        }
        
        return jsonify({
            'success': True,
            'session_id': session.id,
            'status': session.status,
            'session': session_data
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error getting session: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to get chat session'
        }), 500

@bp.route('/api/sessions/<int:session_id>/close', methods=['POST'])
@login_required
def api_close_session(session_id):
    """Close a chat session"""
    try:
        # Get session
        session = ChatSession.query.get(session_id)
        if not session:
            return jsonify({
                'success': False,
                'message': 'Session not found'
            }), 404
        
        # Check if user is participant in this session
        # Customers may send to their own sessions.
        if not current_user.is_admin:
            if session.customer_id != current_user.id:
                return jsonify({
                    'success': False,
                    'message': 'Access denied'
                }), 403
        else:
            # Admins may only send messages for sessions that are assigned to them
            # This enforces that sessions remain in 'waiting' until explicitly assigned.
            if session.agent_id is None or session.agent_id != current_user.id:
                return jsonify({
                    'success': False,
                    'message': 'Only the assigned agent may send messages for this session'
                }), 403
        
        # Update session status
        session.status = 'closed'
        session.closed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Emit event for real-time update
        socketio.emit('session_closed', {
            'session_id': session_id,
            'message': 'This chat session has been closed'
        }, room=f'session_{session_id}')
        
        # Also emit to admins
        socketio.emit('session_closed', {
            'session_id': session_id,
            'message': 'This chat session has been closed'
        }, room='admins')
        
        return jsonify({
            'success': True,
            'message': 'Chat session closed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error closing session: {str(e)}')
        return jsonify({
            'success': False,
            'message': 'Failed to close chat session'
        }), 500

@bp.route('/api/sessions/<int:session_id>', methods=['DELETE'])
@login_required
def api_delete_session(session_id):
    """Delete a chat session"""
    try:
        # Get session
        session = ChatSession.query.get(session_id)
        if not session:
            return jsonify({
                'success': False,
                'message': 'Session not found'
            }), 404
        
        # Check if user is participant in this session
        if (session.customer_id != current_user.id and
            session.agent_id != current_user.id and
            not current_user.is_admin):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Delete all messages in the session
        # Delete dependent notifications first (they reference the session FK)
        ChatNotification.query.filter_by(session_id=session_id).delete()

        # Delete all messages in the session
        ChatMessage.query.filter_by(session_id=session_id).delete()
        
        # Delete the session (handle SQLAlchemy errors explicitly)
        try:
            db.session.delete(session)
            db.session.commit()
        except (SQLAlchemyError, IntegrityError) as db_err:
            # Rollback and log full exception with stacktrace for diagnostics
            db.session.rollback()
            current_app.logger.exception(f"SQLAlchemy error deleting session %s: %s", session_id, str(db_err))
            return jsonify({
                'success': False,
                'message': 'Database error deleting chat session'
            }), 500
        
        # Emit event for real-time update
        socketio.emit('session_deleted', {
            'session_id': session_id
        }, room='admins')

        # Also notify the customer widget (room for the session) to clear
        # its saved session and local history. This ensures that when an
        # admin deletes the session from the admin UI the customer's
        # floating widget clears its localStorage and UI state.
        try:
            socketio.emit('clear_customer_session', {
                'session_id': session_id
            }, room=f'session_{session_id}')
        except Exception:
            # non-fatal: don't block the API if socket emit fails
            pass
        
        return jsonify({
            'success': True,
            'message': 'Chat session deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting session: {str(e)}')
        return jsonify({
            'success': False,
            'message': 'Failed to delete chat session'
        }), 500

@bp.route('/api/sessions/<int:session_id>/assign', methods=['POST'])
@login_required
def api_assign_session(session_id):
    """Assign an admin to a chat session"""
    try:
        # Check if user is admin
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Get session
        session = ChatSession.query.get(session_id)
        if not session:
            return jsonify({
                'success': False,
                'message': 'Session not found'
            }), 404
        
        # Check if session is already assigned
        if session.agent_id and session.status == 'active':
            return jsonify({
                'success': False,
                'message': 'Session already assigned to an agent'
            }), 400
        
        # Assign session to current admin
        session.agent_id = current_user.id
        session.status = 'active'
        session.assigned_at = datetime.utcnow()
        
        db.session.commit()
        
        # Prepare session data for response
        session_data = {
            'id': session.id,
            'customer_id': session.customer_id,
            'customer_name': f"{session.customer.first_name} {session.customer.last_name}" if session.customer else "Unknown",
            'agent_id': session.agent_id,
            'agent_name': f"{session.agent.first_name} {session.agent.last_name}" if session.agent else "Unassigned",
            'status': session.status,
            'subject': session.subject,
            'priority': session.priority,
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'updated_at': session.updated_at.isoformat() if session.updated_at else None,
            'assigned_at': session.assigned_at.isoformat() if session.assigned_at else None
        }
        
        # Emit event for real-time update
        socketio.emit('session_updated', {
            'session_id': session_id,
            'status': 'active',
            'agent_id': current_user.id,
            'agent_name': f"{current_user.first_name} {current_user.last_name}",
            'message': f"Chat assigned to {current_user.first_name} {current_user.last_name}"
        }, room=f'session_{session_id}')
        
        # Also emit to admins
        socketio.emit('session_updated', {
            'session_id': session_id,
            'status': 'active',
            'agent_id': current_user.id,
            'agent_name': f"{current_user.first_name} {current_user.last_name}"
        }, room='admins')
        
        # Create a ChatNotification for the customer so their notification list is updated
        try:
            if session.customer_id:
                notification = ChatNotification(
                    user_id=session.customer_id,
                    session_id=session.id,
                    notification_type='session_assigned',
                    title='Support agent assigned',
                    message=f"{current_user.first_name} {current_user.last_name} has joined your chat",
                    is_read=False
                )
                db.session.add(notification)
                db.session.commit()
        except Exception:
            # Non-fatal: continue even if notification persistence fails
            db.session.rollback()

        # Emit explicit 'session_assigned' event to the session room so connected customers get an immediate notice
        try:
            socketio.emit('session_assigned', {
                'session_id': session.id,
                'agent_id': current_user.id,
                'agent_name': f"{current_user.first_name} {current_user.last_name}",
                'message': f"{current_user.first_name} {current_user.last_name} has joined the chat"
            }, room=f'session_{session.id}')
        except Exception:
            pass
        
        return jsonify({
            'success': True,
            'message': 'Chat session assigned successfully',
            'session': session_data
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error assigning session: {str(e)}')
        return jsonify({
            'success': False,
            'message': 'Failed to assign chat session'
        }), 500

# Canned Response Routes

@bp.route('/api/canned-responses', methods=['GET'])
@login_required
def api_get_canned_responses():
    """Get all active canned responses"""
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Get all active canned responses
        responses = CannedResponse.query.filter_by(is_active=True).all()
        
        # Convert to dictionary format
        responses_data = [response.to_dict() for response in responses]
        
        return jsonify({
            'success': True,
            'responses': responses_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting canned responses: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to get canned responses'
        }), 500

@bp.route('/api/canned-responses', methods=['POST'])
@login_required
def api_create_canned_response():
    """Create a new canned response"""
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Get request data
        data = request.get_json()
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        category = data.get('category', '').strip()
        
        # Validate required fields
        if not title or not content:
            return jsonify({
                'success': False,
                'message': 'Title and content are required'
            }), 400
        
        # Create canned response
        response = CannedResponse(
            title=title,
            content=content,
            category=category
        )
        
        db.session.add(response)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Canned response created successfully',
            'response': response.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating canned response: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to create canned response'
        }), 500

@bp.route('/api/canned-responses/<int:response_id>', methods=['PUT'])
@login_required
def api_update_canned_response(response_id):
    """Update a canned response"""
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Get canned response
        response = CannedResponse.query.get(response_id)
        if not response:
            return jsonify({
                'success': False,
                'message': 'Canned response not found'
            }), 404
        
        # Get request data
        data = request.get_json()
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        category = data.get('category', '').strip()
        is_active = data.get('is_active', response.is_active)
        
        # Update fields
        if title:
            response.title = title
        if content:
            response.content = content
        if category:
            response.category = category
        response.is_active = is_active
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Canned response updated successfully',
            'response': response.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating canned response: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to update canned response'
        }), 500

@bp.route('/api/canned-responses/<int:response_id>', methods=['DELETE'])
@login_required
def api_delete_canned_response(response_id):
    """Delete a canned response"""
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Get canned response
        response = CannedResponse.query.get(response_id)
        if not response:
            return jsonify({
                'success': False,
                'message': 'Canned response not found'
            }), 404
        
        # Delete response
        db.session.delete(response)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Canned response deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting canned response: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete canned response'
        }), 500

# Chat Analytics Routes

@bp.route('/api/analytics/today', methods=['GET'])
@login_required
def api_get_today_analytics():
    """Get today's chat analytics"""
    try:
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        from datetime import date
        
        # Get or create today's analytics record
        today = date.today()
        analytics = ChatAnalytics.query.filter_by(date=today).first()
        
        if not analytics:
            # Create new record with default values
            analytics = ChatAnalytics(
                date=today,
                total_chats=0,
                chats_resolved=0,
                chats_transferred=0,
                total_messages=0,
                avg_response_time=0,
                avg_resolution_time=0,
                customer_satisfaction=0,
                conversion_chats_to_sales=0,
                total_sales_from_chat=0
            )
            db.session.add(analytics)
            db.session.commit()
        
        # Calculate conversion rate
        conversion_rate = analytics.get_conversion_rate()
        
        # Prepare response data
        analytics_data = {
            'date': analytics.date.isoformat(),
            'total_chats': analytics.total_chats,
            'chats_resolved': analytics.chats_resolved,
            'chats_transferred': analytics.chats_transferred,
            'total_messages': analytics.total_messages,
            'avg_response_time': analytics.avg_response_time,
            'avg_resolution_time': analytics.avg_resolution_time,
            'customer_satisfaction': float(analytics.customer_satisfaction) if analytics.customer_satisfaction else 0,
            'conversion_chats_to_sales': analytics.conversion_chats_to_sales,
            'total_sales_from_chat': float(analytics.total_sales_from_chat) if analytics.total_sales_from_chat else 0,
            'conversion_rate': conversion_rate
        }
        
        return jsonify({
            'success': True,
            'analytics': analytics_data
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error getting today's analytics: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to get analytics'
        }), 500

@bp.route('/api/sessions/<int:session_id>/messages', methods=['GET'])
@login_required
def api_get_session_messages(session_id):
    """Get messages for a specific chat session"""
    try:
        # Verify session exists and user has access
        session = ChatSession.query.get(session_id)
        if not session:
            return jsonify({
                'success': False,
                'message': 'Session not found'
            }), 404
        
        # Check if user is participant in this session
        if (session.customer_id != current_user.id and 
            session.agent_id != current_user.id and 
            not current_user.is_admin):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Get messages
        messages = ChatMessage.query.filter_by(session_id=session_id)\
            .order_by(ChatMessage.created_at.asc()).all()
        
        # Convert messages to dictionary format
        messages_data = []
        for message in messages:
            message_data = {
                'id': message.id,
                'session_id': message.session_id,
                'sender_id': message.sender_id,
                'sender_name': f"{message.sender.first_name} {message.sender.last_name}",
                'sender_type': 'agent' if message.sender.is_admin else 'customer',
                'message': message.message,
                'message_type': message.message_type,
                'attachment_url': message.attachment_url,
                'is_read': message.is_read,
                'created_at': message.created_at.isoformat() if message.created_at else None
            }
            messages_data.append(message_data)
        
        return jsonify({
            'success': True,
            'messages': messages_data
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting session messages: {str(e)}')
        return jsonify({
            'success': False,
            'message': 'Failed to get session messages'
        }), 500

@bp.route('/api/sessions/<int:session_id>/messages', methods=['POST'])
@login_required
def api_send_message(session_id):
    """Send a message in a chat session"""
    try:
        # Verify session exists and user has access
        session = ChatSession.query.get(session_id)
        if not session:
            return jsonify({
                'success': False,
                'message': 'Session not found'
            }), 404
        
        # Check if user is participant in this session
        if (session.customer_id != current_user.id and 
            session.agent_id != current_user.id and 
            not current_user.is_admin):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Get message content
        data = request.get_json()
        message_content = data.get('message', '').strip()
        
        if not message_content:
            return jsonify({
                'success': False,
                'message': 'Message content is required'
            }), 400
        
        # Create message
        message = ChatMessage(
            session_id=session_id,
            sender_id=current_user.id,
            message=message_content,
            message_type='text'
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Prepare message data for response
        message_data = {
            'id': message.id,
            'session_id': message.session_id,
            'sender_id': message.sender_id,
            'sender_name': f"{message.sender.first_name} {message.sender.last_name}",
            'sender_type': 'agent' if message.sender.is_admin else 'customer',
            'message': message.message,
            'message_type': message.message_type,
            'attachment_url': message.attachment_url,
            'is_read': message.is_read,
            'created_at': message.created_at.isoformat() if message.created_at else None
        }
        
        # Emit event for real-time update
        socketio.emit('message_sent', {
            'session_id': session_id,
            'message': message_data
        }, room=f'session_{session_id}')
        
        # Also emit to admins
        socketio.emit('message_sent', {
            'session_id': session_id,
            'message': message_data
        }, room='admins')
        
        return jsonify({
            'success': True,
            'message': 'Message sent successfully',
            'message_data': message_data
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error sending message: {str(e)}')
        return jsonify({
            'success': False,
            'message': 'Failed to send message'
        }), 500


@bp.route('/api/sessions/<int:session_id>/mark_read', methods=['POST'])
@login_required
def api_mark_session_read(session_id):
    """Mark all messages in a session as read for the current user (except their own messages)
    and notify connected clients so unread badges can be cleared in real-time."""
    try:
        session = ChatSession.query.get(session_id)
        if not session:
            return jsonify({'success': False, 'message': 'Session not found'}), 404

        # Permission: admins can mark reads for sessions they are assigned to or all (admins)
        if not current_user.is_admin:
            # Customers may only mark their own sessions as read
            if session.customer_id != current_user.id:
                return jsonify({'success': False, 'message': 'Access denied'}), 403

        # Mark messages as read for this user
        try:
            session.mark_messages_as_read(current_user.id)
        except Exception:
            db.session.rollback()

        # Emit socket event so other connected admin clients (and the session room) can clear badges
        try:
            socketio.emit('session_unread_cleared', {'session_id': session_id}, room='admins')
            socketio.emit('session_unread_cleared', {'session_id': session_id}, room=f'session_{session_id}')
        except Exception:
            # non-fatal
            pass

        return jsonify({'success': True, 'message': 'Marked as read'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error marking session read: {str(e)}')
        return jsonify({'success': False, 'message': 'Failed to mark messages as read'}), 500


@bp.route('/api/sessions/<int:session_id>/messages/<int:message_id>', methods=['DELETE'])
@login_required
def api_delete_message(session_id, message_id):
    """Delete a message. If an admin performs the deletion, also clear the customer's
    chat history and remove the session, emitting socket events so connected
    customer widgets clear their saved state."""
    try:
        # Verify session exists
        session = ChatSession.query.get(session_id)
        if not session:
            return jsonify({'success': False, 'message': 'Session not found'}), 404

        # Verify message exists
        message = ChatMessage.query.get(message_id)
        if not message:
            return jsonify({'success': False, 'message': 'Message not found'}), 404

        # Ensure message belongs to session
        if message.session_id != session.id:
            return jsonify({'success': False, 'message': 'Message does not belong to session'}), 400

        # Permission check: allow admins, the session customer, or the message sender
        if not (current_user.is_admin or session.customer_id == current_user.id or message.sender_id == current_user.id):
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        # If admin is deleting, clear entire session and its messages
        if current_user.is_admin:
            # Delete all messages for the session
            ChatMessage.query.filter_by(session_id=session.id).delete()

            # Delete the session itself
            db.session.delete(session)
            db.session.commit()

            # Notify connected customers to clear local session/messages
            try:
                socketio.emit('clear_customer_session', {'session_id': session_id}, room=f'session_{session_id}')
                # Notify admins to remove session from lists
                socketio.emit('session_deleted', {'session_id': session_id}, room='admins')
            except Exception:
                # non-fatal: don't block on socket emit failures
                pass

            return jsonify({'success': True, 'message': 'Message deleted and session cleared'})

        # Non-admin deleting: delete only the single message
        db.session.delete(message)
        db.session.commit()

        # Emit lightweight event so UIs can remove the message from their view
        try:
            socketio.emit('message_deleted', {'session_id': session_id, 'message_id': message_id}, room=f'session_{session_id}')
            socketio.emit('message_deleted', {'session_id': session_id, 'message_id': message_id}, room='admins')
        except Exception:
            pass

        return jsonify({'success': True, 'message': 'Message deleted successfully'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting message: {str(e)}')
        return jsonify({'success': False, 'message': 'Failed to delete message'}), 500

@bp.route('/widget')
def chat_widget_example():
    """Example page showing how to embed the chat widget"""
    return render_template('chat_widget.html')

@bp.route('/test-widget')
def test_chat_widget():
    """Test page for the chat widget"""
    return render_template('test_chat_widget.html')