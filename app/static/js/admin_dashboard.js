// Admin Dashboard JavaScript
class AdminDashboard {
  constructor() {
    this.currentSessionId = null;
    this.socket = null;
    this.sessions = {};
    this.agents = {};
    this.cannedResponses = [];
    this.isTyping = false;
    this.typingTimeout = null;
  // Timeout used to hide the customer typing indicator UI
  this.customerTypingTimeout = null;
    
this.displayedMessages = new Map(); // Track displayed messages per session to prevent duplicates
  this.skipClearOnClose = null; // session id that should not clear saved selection when we closed it locally
this.initializeDashboard();
this.setupEventListeners();
this.connectToSocket();
this.loadDashboardData();
}

clearSessionListExceptNoSessionsMessage(sessionsList) {
// Clear existing sessions but preserve the "no-sessions-message" div
const noSessionsMessage = sessionsList.querySelector('#no-sessions-message');

// Remove all child nodes except the "no-sessions-message" div
const children = Array.from(sessionsList.children);
children.forEach(child => {
  if (child !== noSessionsMessage) {
    sessionsList.removeChild(child);
  }
});
}
  
  initializeDashboard() {
    // Initialize any UI components
    this.updateDashboardStats();
    
    // Ensure btn-group is properly initialized and visible
    const btnGroup = document.querySelector('.btn-group[role="group"]');
    if (btnGroup) {
      btnGroup.style.display = 'flex';
      btnGroup.style.visibility = 'visible';
    }
    
    // Initially disable action buttons and input group until a session is selected
    this.disableActionButtons();
    this.disableInputGroup();

    // Read current admin identity from the page (rendered in base.html as JSON)
    try {
      const currentUserEl = document.getElementById('currentUserData');
      if (currentUserEl) {
        const parsed = JSON.parse(currentUserEl.textContent);
        this.currentAdminId = parsed && parsed.id ? String(parsed.id) : null;
      } else {
        this.currentAdminId = null;
      }
    } catch (e) {
      this.currentAdminId = null;
    }

    // Load saved chat filter (all|unassigned|mine|high)
    try {
      const savedFilter = localStorage.getItem('adminChatFilter');
      this.currentFilter = savedFilter || 'all';
    } catch (e) {
      this.currentFilter = 'all';
    }
    // Apply the filter UI state now (renderChatSessions will re-apply after render)
    this.applyFilterUI(this.currentFilter);
  }
  
  setupEventListeners() {
    // Auto-assign toggle
    var autoAssignToggle = document.getElementById('auto-assign-toggle');
    if (autoAssignToggle) {
      // Load saved state
      this.loadAutoAssignState();
      
      autoAssignToggle.addEventListener('change', (e) => {
        this.toggleAutoAssign(e.target.checked);
        // Save state
        this.saveAutoAssignState(e.target.checked);
      });
    }
    
    // Chat session filter
    var filterItems = document.querySelectorAll('[data-filter]');
    filterItems.forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        // Support clicks on inner elements by walking up to element with data-filter
        let el = e.target;
        while (el && !el.dataset.filter) el = el.closest('[data-filter]');
        const filter = el ? el.dataset.filter : null;
        if (filter) {
          this.currentFilter = filter;
          try { localStorage.setItem('adminChatFilter', filter); } catch (e) {}
          this.filterChatSessions(filter);
          this.applyFilterUI(filter);
        }
      });
    });
    
    // Transfer chat button
    var transferBtn = document.getElementById('transfer-chat-btn');
    if (transferBtn) {
      transferBtn.addEventListener('click', () => {
        this.transferChat();
      });
    }
    
    // Assign chat button
    const assignBtn = document.getElementById('assign-chat-btn');
    if (assignBtn) {
      assignBtn.addEventListener('click', () => {
        this.assignChat();
      });
    }
    
    // Close chat button
    var closeBtn = document.getElementById('close-chat-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        this.closeChat();
      });
    }
    
    // Canned responses select
    const cannedSelect = document.getElementById('canned-responses-select');
    if (cannedSelect) {
      cannedSelect.addEventListener('change', (e) => {
        this.insertCannedResponse(e.target.value);
      });
    }
    
    // Attachment button
    const attachmentBtn = document.getElementById('admin-attachment-btn');
    if (attachmentBtn) {
      attachmentBtn.addEventListener('click', () => {
        this.openAttachmentDialog();
      });
    }
    
    // Remove attachment button
    const removeAttachmentBtn = document.getElementById('remove-attachment-btn');
    if (removeAttachmentBtn) {
      removeAttachmentBtn.addEventListener('click', () => {
        this.removeAttachment();
      });
    }
    
    // Message form submission
    const messageForm = document.getElementById('admin-message-form');
    if (messageForm) {
      messageForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.sendMessage();
      });
    }
    
    // Message input typing
    const messageInput = document.getElementById('admin-message-input');
    if (messageInput) {
      messageInput.addEventListener('input', () => {
        this.handleTyping();
      });
    }
  }
  
  connectToSocket() {
    // Connect to Socket.IO server
    this.socket = io();
    
    // Listen for events
    this.socket.on('connect', () => {
      this.socket.emit('join_room', 'admins');
      
      // After a short delay, join all existing session rooms
      // This ensures we receive real-time messages for all sessions
      setTimeout(() => {
        Object.keys(this.sessions).forEach(sessionId => {
          const session = this.sessions[sessionId];
          if (session) {
            // Join session rooms silently to avoid emitting "Admin Joined" notifications
            this.socket.emit('join_session', {
              session_id: sessionId,
              customer_name: session.customer_name || 'Customer',
              silent: true
            });
          }
        });
      }, 1000);
    });
    
    this.socket.on('new_chat_session', (data) => {
      this.addNewChatSession(data);
    });
    
    this.socket.on('message_sent', (data) => {
      try {
        const sessionId = data && data.session_id ? String(data.session_id) : null;

        // Normalize message text and created_at in case server wraps message inside `message` key
        let messageObj = data;
        if (data && data.message && typeof data.message === 'object') {
          messageObj = Object.assign({}, data.message);
          messageObj.session_id = data.session_id;
        }

        // If admin doesn't have this session yet, create a lightweight waiting session entry
        if (sessionId && !this.sessions[sessionId]) {
          const lastMsgText = messageObj && (messageObj.message || (typeof messageObj.message === 'string' ? messageObj.message : ''));
          const lastMsgTime = messageObj && (messageObj.created_at || new Date().toISOString());

          this.sessions[sessionId] = {
            id: sessionId,
            customer_name: messageObj && messageObj.sender_name ? messageObj.sender_name : 'Customer',
            last_message: lastMsgText || 'New message',
            last_message_time: lastMsgTime,
            status: 'waiting',
            unread_count: 1
          };

          // Join the session room to receive further session-scoped events
          if (this.socket) {
            this.socket.emit('join_session', {
              session_id: sessionId,
              customer_name: this.sessions[sessionId].customer_name || 'Customer',
              silent: true
            });
          }

          // Re-render so the new session appears in the list immediately (new sessions show at top thanks to sorting)
          this.renderChatSessions();
          this.updateSessionCounts();
        } else if (sessionId && this.sessions[sessionId]) {
          // If a message arrives for an existing but unassigned/closed session, ensure it stays 'waiting'
          const session = this.sessions[sessionId];
          if (session && session.status !== 'active') {
            session.status = 'waiting';
            // When not active, make sure admin can't type in that session
            if (String(this.currentSessionId) === String(sessionId)) {
              this.disableInputGroup();
            }
          }
        }

        // Finally display the message (this will update previews and badges)
        this.displayMessage(messageObj);
      } catch (e) {
        // Fall back to original behavior on error
        try { this.displayMessage(data); } catch (e2) {}
      }
    });

    // Listen for message deletions so UI can update in real-time
    this.socket.on('message_deleted', (data) => {
      try {
        const sessionId = String(data.session_id);
        const messageId = String(data.message_id);

        // Remove message element from current chat if present
        const messagesContainer = document.getElementById('chat-messages-container');
        if (messagesContainer) {
          const msgBtn = messagesContainer.querySelector(`.message-delete-btn[data-message-id="${messageId}"]`);
          if (msgBtn) {
            const msgEl = msgBtn.closest('.message');
            if (msgEl && msgEl.parentNode) msgEl.parentNode.removeChild(msgEl);
          }
        }

        // Clear displayed messages cache for the session so next load is fresh
        this.clearDisplayedMessagesForSession(sessionId);

        // If this session was deleted by admin, handle session deletion UI
        if (data.session_deleted) {
          if (this.sessions[sessionId]) delete this.sessions[sessionId];
          if (this.loadSelectedSession() == sessionId) this.clearSelectedSession();
          if (this.currentSessionId === sessionId) {
            this.currentSessionId = null;
            this.updateSelectedSessionUI(null);
          }
          this.renderChatSessions();
          this.updateSessionCounts();
        }
      } catch (e) {
        // ignore
      }
    });
    
    this.socket.on('user_typing', (data) => {
      this.showCustomerTyping(data);
    });
    
    this.socket.on('session_updated', (data) => {
      this.updateSessionStatus(data);
    });
    
    this.socket.on('agent_status_changed', (data) => {
      this.updateAgentStatus(data);
    });
    
    this.socket.on('admin_notification', (data) => {
      this.showNotification(data);
    });
    
    this.socket.on('session_closed', (data) => {
      // Update session status in our data store
      if (this.sessions[data.session_id]) {
        this.sessions[data.session_id].status = 'closed';
      }
      
      // Clear saved session only if this client didn't just close it.
      // When this client closes a session we keep it selected so a later "waiting" update
      // (customer reply) can immediately re-enable the btn-group without a page refresh.
      if (this.skipClearOnClose === data.session_id) {
        // Clear the flag but don't clear the saved selection
        this.skipClearOnClose = null;
      } else {
        if (this.loadSelectedSession() == data.session_id) {
          this.clearSelectedSession();
        }
      }
      
      // Clear displayed messages for this session
      this.clearDisplayedMessagesForSession(data.session_id);
      
  // If this was the current session, show closed message
  if (this.currentSessionId === data.session_id) {
        const messagesContainer = document.getElementById('chat-messages-container');
        if (messagesContainer) {
          // Immediately reset the chat area to the centered placeholder so the admin
          // sees the 'Select a conversation to start chatting' message when the
          // session is closed. We keep the session selected in memory so it can be
          // reopened if the customer replies.
          messagesContainer.innerHTML = `\n            <div class="text-center text-muted d-flex align-items-center justify-content-center h-100" id="no-chat-selected">\n              <div>\n                <i class="fas fa-comment-alt fa-3x mb-3"></i>\n                <p>Select a conversation to start chatting</p>\n              </div>\n            </div>\n          `;
        }
        
        // Disable both action buttons and input fields immediately for the selected session
        const messageInput = document.getElementById('admin-message-input');
        const sendBtn = document.getElementById('admin-send-btn');
        if (messageInput) messageInput.disabled = true;
        if (sendBtn) {
          sendBtn.disabled = true;
          sendBtn.classList.add('disabled');
          sendBtn.setAttribute('disabled', 'disabled');
        }
        // Also disable the action buttons (btn-group) so admins can't assign/transfer/close a closed session
        this.disableActionButtons();
      }
      
  // Update session status in UI
  this.updateSessionStatus({ session_id: data.session_id, status: 'closed' });
    });
    
    this.socket.on('session_deleted', (data) => {
      // Remove session from our data store
      if (this.sessions[data.session_id]) {
        delete this.sessions[data.session_id];
      }
      
      // Clear saved session if it's the deleted session
      if (this.loadSelectedSession() == data.session_id) {
        this.clearSelectedSession();
      }
      
      // Clear displayed messages for this session
      this.clearDisplayedMessagesForSession(data.session_id);
      
      // If this was the current session, clear the UI
      if (this.currentSessionId === data.session_id) {
        this.currentSessionId = null;
        this.updateSelectedSessionUI(null);
        const messagesContainer = document.getElementById('chat-messages-container');
        if (messagesContainer) {
          messagesContainer.innerHTML = `
            <div class="text-center text-muted d-flex align-items-center justify-content-center h-100" id="no-chat-selected">
              <div>
                <i class="fas fa-comment-alt fa-3x mb-3"></i>
                <p>Select a conversation to start chatting</p>
              </div>
            </div>
          `;
        }
        const contextPanel = document.getElementById('customer-context-panel');
        if (contextPanel) {
          contextPanel.innerHTML = `
            <div class="text-center text-muted" id="no-customer-selected">
              <i class="fas fa-user fa-2x mb-2"></i>
              <p>Select a conversation to view customer details</p>
            </div>
          `;
        }
        const transferBtn = document.getElementById('transfer-chat-btn');
        const closeBtn = document.getElementById('close-chat-btn');
        const assignBtn = document.getElementById('assign-chat-btn');
        if (transferBtn) transferBtn.disabled = true;
        if (closeBtn) closeBtn.disabled = true;
        if (assignBtn) assignBtn.disabled = true;
      }
      
      // Re-render session list
      this.renderChatSessions();
      this.updateSessionCounts();
    });

    // When server notifies that unread for a session was cleared (someone read it)
    this.socket.on('session_unread_cleared', (data) => {
      try {
        const sessId = data.session_id;
        // Update local model
        if (this.sessions && this.sessions[sessId]) {
          this.sessions[sessId].unread_count = 0;
        }

        // Remove badge from UI if present
        const sessionElement = document.querySelector(`[data-session-id="${sessId}"]`);
        if (sessionElement) {
          const badge = sessionElement.querySelector('.session-unread-badge');
          if (badge && badge.parentNode) {
            badge.parentNode.removeChild(badge);
          }
        }

        // Refresh counts
        this.updateSessionCounts();
      } catch (e) {
        // ignore
      }
    });
  }
  
  loadDashboardData() {
    // Load initial data for the dashboard
    Promise.all([
      this.loadChatSessions(),
      this.loadAgents(),
      this.loadCannedResponses(),
      this.loadDashboardStats()
    ]).then(() => {
      // After all data is loaded, check if there's a saved session to reselect
      const savedSessionId = this.loadSelectedSession();
      if (savedSessionId && this.sessions[savedSessionId]) {
        // Check if the saved session is closed
        const savedSession = this.sessions[savedSessionId];
        if (savedSession.status === 'closed') {
          // Clear the saved session if it's closed and disable buttons
          this.clearSelectedSession();
          setTimeout(() => {
            this.disableActionButtons();
            this.disableInputGroup();
          }, 100);
        } else {
          // Delay the session selection to ensure UI is fully loaded
          setTimeout(() => {
            this.selectChatSession(savedSessionId);
          }, 100);
        }
      } else {
        // No saved session, disable action buttons
        setTimeout(() => {
          this.disableActionButtons();
          this.disableInputGroup();
        }, 100);
      }
    }).catch(error => {
    });
  }
  
  loadChatSessions() {
    return fetch('/messenger/api/sessions')
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          this.sessions = {};
          data.sessions.forEach(session => {
            this.sessions[session.id] = session;
            
            // Join the session room to receive real-time messages
            if (this.socket) {
              this.socket.emit('join_session', {
                session_id: session.id,
                customer_name: session.customer_name || 'Customer'
              });
            }
          });
          this.renderChatSessions();
          this.updateSessionCounts();
        }
      })
      .catch(error => {
      });
  }
  
  loadAgents() {
    return fetch('/messenger/api/agents')
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          // Normalize agent map keys to strings and ensure sensible defaults
          this.agents = {};
          data.agents.forEach(agent => {
            const agentId = String(agent.id || agent.agent_id || agent.user_id);
            this.agents[agentId] = Object.assign({
              is_available: !!agent.is_available,
              active_sessions: agent.active_sessions || 0
            }, agent);
          });
          this.renderAgents();
          this.updateAgentCounts();
        }
      })
      .catch(error => {
      });
  }
  
  loadCannedResponses() {
    return fetch('/messenger/api/canned-responses')
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          this.cannedResponses = data.responses;
          this.renderCannedResponses();
        }
      })
      .catch(error => {
      });
  }
  
  loadDashboardStats() {
    return fetch('/messenger/api/analytics/today')
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          this.updateDashboardStats(data.data);
        }
      })
      .catch(error => {
      });
  }
  
  renderChatSessions() {
    const sessionsList = document.getElementById('chat-sessions-list');
    if (!sessionsList) return;
    
    // Check if there are any sessions
    if (Object.keys(this.sessions).length === 0) {
      // Clear existing sessions but preserve the "no-sessions-message" div
      this.clearSessionListExceptNoSessionsMessage(sessionsList);

      // Make sure the no-sessions template is visible
      const noSessionsMessage = document.getElementById('no-sessions-message');
      if (noSessionsMessage) {
        noSessionsMessage.classList.remove('d-none');
        noSessionsMessage.style.display = '';
      }

      // Reset the chat pane to the 'no chat selected' placeholder
      const messagesContainer = document.getElementById('chat-messages-container');
      if (messagesContainer) {
        messagesContainer.innerHTML = `\n          <div class="text-center text-muted d-flex align-items-center justify-content-center h-100" id="no-chat-selected">\n            <div>\n              <i class="fas fa-comment-alt fa-3x mb-3"></i>\n              <p>No active conversations</p>\n            </div>\n          </div>\n        `;
      }

      // Hide action buttons since there are no sessions
      const btnGroup = document.querySelector('.btn-group[role="group"]');
      if (btnGroup) {
        btnGroup.style.display = 'none';
        btnGroup.classList.add('d-none');
      }

      // Clear any stored selection and update counts
      try { this.clearSelectedSession(); } catch (e) {}
      this.updateSessionCounts();

      return;
    }
    
    // Hide no sessions message
    const noSessionsMessage = document.getElementById('no-sessions-message');
    if (noSessionsMessage) {
      // noSessionsMessage.classList.add('d-none');
      noSessionsMessage.style.display = 'none';
    }
    
    // Clear existing sessions (but keep the "no-sessions-message" div)
    this.clearSessionListExceptNoSessionsMessage(sessionsList);
    
    // Render each session, sorted by most recent activity (last_message_time or created_at)
    const sessionsArray = Object.values(this.sessions || {});
    sessionsArray.sort((a, b) => {
      const aTime = new Date(a.last_message_time || a.created_at || 0).getTime();
      const bTime = new Date(b.last_message_time || b.created_at || 0).getTime();
      return bTime - aTime; // newest first
    });

    sessionsArray.forEach(session => {
      const sessionElement = this.createSessionElement(session);
      sessionsList.appendChild(sessionElement);
    });
    
    // Apply any active filter after rendering
    try {
      this.filterChatSessions(this.currentFilter || 'all');
      this.applyFilterUI(this.currentFilter || 'all');
    } catch (e) {}
  }
  
  createSessionElement(session) {
    const sessionElement = document.createElement('div');
  sessionElement.className = `list-group-item list-group-item-action chat-session-item ${session.id === this.currentSessionId ? 'active' : ''}`;
  sessionElement.dataset.sessionId = String(session.id);
  // Add dataset attributes used by filtering
  sessionElement.dataset.agentId = session.agent_id ? String(session.agent_id) : '';
  sessionElement.dataset.priority = session.priority ? String(session.priority) : '';
  if (!session.agent_id) sessionElement.classList.add('unassigned');
  if (session.priority === 'high') sessionElement.classList.add('high-priority');
    
    // Handle missing or undefined last message data
    const lastMessage = session.last_message || 'No messages yet';
    const lastMessageTime = session.last_message_time ? this.formatTime(session.last_message_time) : '';
    
    sessionElement.innerHTML = `
      <div class="d-flex w-100 justify-content-between">
        <h6 class="mb-1 session-customer-name">${session.customer_name}</h6>
        ${lastMessageTime ? `<small class="session-time">${lastMessageTime}</small>` : ''}
      </div>
      <p class="mb-1 session-last-message">${lastMessage}</p>
      <div class="d-flex justify-content-between align-items-center">
        <small class="text-muted">
          ${session.agent_name ? `Assigned to ${session.agent_name}` : 'Unassigned'}
        </small>
        <div>
          ${session.unread_count > 0 ? `<span class="session-unread-badge me-2">${session.unread_count}</span>` : ''}
          <button class="btn btn-sm btn-outline-danger delete-session-btn" data-session-id="${session.id}">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      </div>
    `;
    
    // Add click event to select session
    sessionElement.addEventListener('click', (e) => {
      // Don't select session if clicking on delete button
      if (e.target.closest('.delete-session-btn')) {
        return;
      }
      
      // Immediately show the btn-group when clicking on a session
      const btnGroup = document.querySelector('.btn-group[role="group"]');
      if (btnGroup) {
        btnGroup.style.display = 'flex';
        btnGroup.style.visibility = 'visible';
        btnGroup.classList.remove('d-none');
      }
      
      // Enable action buttons immediately
      this.enableActionButtons();
      
      this.selectChatSession(session.id);
    });
    
    // Add click event for delete button
    const deleteBtn = sessionElement.querySelector('.delete-session-btn');
    if (deleteBtn) {
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.deleteSession(session.id);
      });
    }
    
    return sessionElement;
  }
  
  selectChatSession(sessionId) {
    // Update current session
    this.currentSessionId = sessionId;
    
    // Save selected session to localStorage
    this.saveSelectedSession(sessionId);
    
    // Immediately make btn-group visible
    // This must happen FIRST to ensure immediate display
    const btnGroup = document.querySelector('.btn-group[role="group"]');
    if (btnGroup) {
      btnGroup.style.display = 'flex';
      btnGroup.style.visibility = 'visible';
      btnGroup.classList.remove('d-none');
    }
    
    // Enable action buttons immediately
    this.enableActionButtons();
    this.disableInputGroup();

    // Update UI to show selected session
    this.updateSelectedSessionUI(sessionId);
    
    // Load messages for this session
    this.loadSessionMessages(sessionId);

    // Load customer context for the selected session (if available)
    try {
      this.loadCustomerContext(sessionId);
    } catch (e) {
      // ignore errors from context loading
    }

    // Mark messages as read on the server for this session so unread counts clear
    try {
      fetch(`/messenger/api/sessions/${sessionId}/mark_read`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
        }
      }).then(() => {
        // Clear unread badge locally as well
        const sessionElement = document.querySelector(`[data-session-id="${sessionId}"]`);
        if (sessionElement) {
          const badge = sessionElement.querySelector('.session-unread-badge');
          if (badge && badge.parentNode) {
            badge.parentNode.removeChild(badge);
          }
        }
        if (this.sessions[sessionId]) this.sessions[sessionId].unread_count = 0;
        this.updateSessionCounts();
      }).catch(() => {});
    } catch (e) {}
    
    // Initialize displayed messages for this session if not already present
    // Ensure a Set exists for this session to track displayed message identifiers
    if (!this.displayedMessages.has(sessionId)) {
      this.displayedMessages.set(sessionId, new Set());
    }
    
    // Load customer context
    this.loadCustomerContext(sessionId);

    // Join session room
    // When admin selects a session from the list, join silently so we don't trigger a join toast
    this.socket.emit('join_session', {
      session_id: sessionId,
      customer_name: this.sessions[sessionId] ? this.sessions[sessionId].customer_name : 'Customer',
      silent: true
    });
    
    // Also join the admins room to receive notifications
    this.socket.emit('join_room', 'admins');

    // Check session status and agent assignment to enable/disable buttons and input accordingly
    const session = this.sessions[sessionId];
    console.log('Session selection - Session status:', session ? session.status : 'no session', 'Session ID:', sessionId);

    if (session && session.status === 'closed') {
      // If session is closed, disable both btn-group and input-group until customer sends message
      console.log('Disabling buttons - session is closed');
      this.disableActionButtons();
      this.disableInputGroup();
    } else if (session && session.status === 'waiting') {
      // Waiting sessions: allow actions (assign/transfer) but keep input disabled until assigned
      console.log('Session is waiting - actions enabled, input disabled until assignment');
      this.enableActionButtons();
      this.disableInputGroup();
    } else if (session && session.status === 'active') {
      // Active sessions: enable actions. Input enabled only if an agent is assigned.
      console.log('Session is active - enabling actions; enabling input only if assigned');
      this.enableActionButtons();
      if (session.agent_id) {
        this.enableInputGroup();
      } else {
        this.disableInputGroup();
      }
      
      // If session is already assigned, disable the assign button specifically
      if (session.agent_id) {
        console.log('Disabling assign button - session already assigned');
        const assignBtn = document.getElementById('assign-chat-btn');
        if (assignBtn) {
          assignBtn.disabled = true;
          assignBtn.classList.add('disabled');
          assignBtn.setAttribute('disabled', 'disabled');
        }
      }
    } else {
      // Default: disable actions and input
      console.log('Default: disabling actions and input - session status:', session ? session.status : 'no session');
      this.disableActionButtons();
      this.disableInputGroup();
    }
  }
  
  enableActionButtons() {
    // Enable the action buttons immediately
    const assignBtn = document.getElementById('assign-chat-btn');
    const transferBtn = document.getElementById('transfer-chat-btn');
    const closeBtn = document.getElementById('close-chat-btn');
    
    // Ensure the btn-group container is visible
    const btnGroup = document.querySelector('.btn-group[role="group"]');
    if (btnGroup) {
      btnGroup.style.display = 'flex';
      btnGroup.style.visibility = 'visible';
      btnGroup.classList.remove('d-none');
    }
    
    // Force enable each button by removing all disabled states
    [assignBtn, transferBtn, closeBtn].forEach(btn => {
      if (btn) {
        // Remove all disabled attributes and classes
        btn.disabled = false;
        btn.classList.remove('disabled');
        btn.removeAttribute('disabled');
        
        // Ensure proper display and interaction
        btn.style.display = 'inline-block';
        btn.style.visibility = 'visible';
        btn.style.pointerEvents = 'auto';
        btn.style.opacity = '1';
        
        // Force remove any Bootstrap disabled classes
        btn.classList.remove('btn-disabled');
      }
    });
    
    console.log('Action buttons enabled:', {
      assign: assignBtn ? !assignBtn.disabled : 'not found',
      transfer: transferBtn ? !transferBtn.disabled : 'not found',
      close: closeBtn ? !closeBtn.disabled : 'not found'
    });
  }
  
  enableInputGroup() {
    // Enable input-group elements
    const attachmentBtn = document.getElementById('admin-attachment-btn');
    const messageInput = document.getElementById('admin-message-input');
    const sendBtn = document.getElementById('admin-send-btn');
    
    if (attachmentBtn) {
      attachmentBtn.disabled = false;
      attachmentBtn.classList.remove('disabled');
      attachmentBtn.removeAttribute('disabled');
    }
    
    if (messageInput) {
      messageInput.disabled = false;
    }
    
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.classList.remove('disabled');
      sendBtn.removeAttribute('disabled');
    }
  }
  
  disableActionButtons() {
    const assignBtn = document.getElementById('assign-chat-btn');
    const transferBtn = document.getElementById('transfer-chat-btn');
    const closeBtn = document.getElementById('close-chat-btn');
    
    [assignBtn, transferBtn, closeBtn].forEach(btn => {
      if (btn) {
        btn.disabled = true;
        btn.classList.add('disabled');
        btn.setAttribute('disabled', 'disabled');
        btn.style.pointerEvents = 'none';
        btn.style.opacity = '0.6';
      }
    });
    
    console.log('Action buttons disabled');
  }
  
  disableInputGroup() {
    // Disable input-group elements
    const attachmentBtn = document.getElementById('admin-attachment-btn');
    const messageInput = document.getElementById('admin-message-input');
    const sendBtn = document.getElementById('admin-send-btn');
    
    if (attachmentBtn) {
      attachmentBtn.disabled = true;
      attachmentBtn.classList.add('disabled');
      attachmentBtn.setAttribute('disabled', 'disabled');
    }
    
    if (messageInput) {
      messageInput.disabled = true;
    }
    
    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.classList.add('disabled');
      sendBtn.setAttribute('disabled', 'disabled');
    }
  }
  
  saveSelectedSession(sessionId) {
    // Save the selected session ID to localStorage
    try {
      localStorage.setItem('adminSelectedSessionId', JSON.stringify(sessionId));
    } catch (e) {
    }
  }
  
  loadSelectedSession() {
    // Load the selected session ID from localStorage
    try {
      const savedSessionId = localStorage.getItem('adminSelectedSessionId');
      if (savedSessionId !== null) {
        return JSON.parse(savedSessionId);
      }
    } catch (e) {
    }
    return null;
  }
  
  clearSelectedSession() {
    // Clear the selected session ID from localStorage
    try {
      localStorage.removeItem('adminSelectedSessionId');
    } catch (e) {
    }
  }
  
  updateSelectedSessionUI(sessionId) {
    // Update active class on session items
    const sessionItems = document.querySelectorAll('.chat-session-item');
    // Safely coerce sessionId to string only when it's defined
    const sid = (sessionId !== null && sessionId !== undefined) ? String(sessionId) : null;
    sessionItems.forEach(item => {
      if (sid !== null && item.dataset.sessionId === sid) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });
    
    // Update chat title and status
  const session = (sessionId !== null && sessionId !== undefined) ? this.sessions[sessionId] : null;
    if (session) {
      const chatTitle = document.getElementById('current-chat-title');
      const chatStatus = document.getElementById('current-chat-status');
      
      if (chatTitle) {
        chatTitle.innerHTML = `<i class="fas fa-comment me-2"></i> Chat with ${session.customer_name}`;
      }
      
      if (chatStatus) {
        chatStatus.textContent = `Status: ${session.status} ${session.agent_name ? `| Assigned to ${session.agent_name}` : ''}`;
      }
      
      // Show chat interface and ensure btn-group is visible
      const noChatSelected = document.getElementById('no-chat-selected');
      if (noChatSelected) {
        noChatSelected.classList.add('d-none');
      }
      
      // Make sure the btn-group is visible by ensuring all buttons are properly displayed
      const btnGroup = document.querySelector('.btn-group[role="group"]');
      if (btnGroup) {
        btnGroup.style.display = '';
        btnGroup.style.visibility = 'visible';
      }
      
      // Ensure individual buttons are visible
      const assignBtn = document.getElementById('assign-chat-btn');
      const transferBtn = document.getElementById('transfer-chat-btn');
      const closeBtn = document.getElementById('close-chat-btn');
      
      [assignBtn, transferBtn, closeBtn].forEach(btn => {
        if (btn) {
          btn.style.display = '';
          btn.style.visibility = 'visible';
        }
      });
      
    } else {
      // No session selected, hide chat interface and disable action buttons
      const noChatSelected = document.getElementById('no-chat-selected');
      if (noChatSelected) {
        noChatSelected.classList.remove('d-none');
      }
      
      // Reset chat title
      const chatTitle = document.getElementById('current-chat-title');
      const chatStatus = document.getElementById('current-chat-status');
      if (chatTitle) {
        chatTitle.innerHTML = `<i class="fas fa-comment me-2"></i> Select a conversation`;
      }
      if (chatStatus) {
        chatStatus.textContent = '';
      }
      
      // Disable action buttons and input group after a short delay to avoid conflicts
      setTimeout(() => {
        this.disableActionButtons();
        this.disableInputGroup();
      }, 100);
    }
  }
  
  loadSessionMessages(sessionId) {
    fetch(`/messenger/api/sessions/${sessionId}/messages`)
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          const messagesContainer = document.getElementById('chat-messages-container');
          if (messagesContainer) {
            messagesContainer.innerHTML = '';
            // Clear displayed messages for this session
            if (this.displayedMessages.has(sessionId)) {
              this.displayedMessages.delete(sessionId);
            }
            this.displayedMessages.set(sessionId, new Set());
            
            data.messages.forEach(message => {
              // Use displayMessage function to ensure proper duplicate prevention
              // We need to add session_id to the message object for displayMessage to work correctly
              const messageWithSessionId = {
                ...message,
                session_id: sessionId
              };
              this.displayMessage(messageWithSessionId);
            });
            this.scrollToBottom(messagesContainer);
          }
        }
      })
      .catch(error => {
      });
  }
  
  loadCustomerContext(sessionId) {
    // Use the session data we already have. If customer context is missing, fetch full detail
    const session = this.sessions[sessionId];
    if (!session) return;

    // If session already contains a customer object or recent_orders array, render immediately
    if (session.customer || Array.isArray(session.recent_orders)) {
      this.renderCustomerContext(session);
      return;
    }

    // Otherwise fetch full session detail and render
    fetch(`/messenger/api/sessions/${sessionId}/detail`)
      .then(resp => resp.json())
      .then(data => {
        if (data && data.success && data.session) {
          // Merge into local cache and render
          try { this.sessions[sessionId] = Object.assign({}, this.sessions[sessionId] || {}, data.session); } catch (e) {}
          this.renderCustomerContext(data.session);
        } else {
          this.renderCustomerContext(session);
        }
      })
      .catch(() => {
        this.renderCustomerContext(session);
      });
  }
  
  renderCustomerContext(sessionData) {
    const contextPanel = document.getElementById('customer-context-panel');
    const noCustomerSelected = document.getElementById('no-customer-selected');
    if (!contextPanel) return;

    // Hide the placeholder if it exists (the panel may have been replaced on first render)
    if (noCustomerSelected) {
      noCustomerSelected.classList.add('d-none');
    }
    
    // Safely render customer information (guard against missing data)
    const customer = sessionData && sessionData.customer ? sessionData.customer : null;
    const recentOrders = sessionData && Array.isArray(sessionData.recent_orders) ? sessionData.recent_orders : [];

    contextPanel.innerHTML = `
      <div class="customer-info-row">
        <span class="customer-info-label">Name:</span>
        <span class="customer-info-value">${customer ? `${customer.first_name || ''} ${customer.last_name || ''}`.trim() : 'Guest'}</span>
      </div>
      <div class="customer-info-row">
        <span class="customer-info-label">Email:</span>
        <span class="customer-info-value">${customer && customer.email ? customer.email : 'N/A'}</span>
      </div>
      <div class="customer-info-row">
        <span class="customer-info-label">Member Since:</span>
        <span class="customer-info-value">${customer && customer.created_at ? this.formatDate(customer.created_at) : '—'}</span>
      </div>
      <div class="customer-info-row">
        <span class="customer-info-label">Last Chat:</span>
        <span class="customer-info-value">${sessionData && sessionData.created_at ? this.formatDate(sessionData.created_at) : '—'}</span>
      </div>
      
      <h6 class="mt-3 mb-2">Recent Orders</h6>
      <div class="order-history">
        ${recentOrders.length > 0 ?
          recentOrders.map(order => `
            <div class="order-item">
              <div class="d-flex justify-content-between">
                <span class="order-number">#${order.order_number}</span>
                <span class="order-status badge bg-${order.payment_status === 'paid' ? 'success' : 'warning'}">${order.payment_status}</span>
              </div>
              <div class="d-flex justify-content-between mt-1">
                <span class="text-muted">$${(order.total_amount || 0).toFixed(2)}</span>
                <span class="text-muted">${order.created_at ? this.formatDate(order.created_at) : ''}</span>
              </div>
            </div>
          `).join('') :
          '<p class="text-muted">No recent orders</p>'
        }
      </div>
    `;
  }
  
  renderAgents() {
    const agentsList = document.getElementById('agents-list');
    if (!agentsList) return;

    agentsList.innerHTML = '';

    Object.entries(this.agents).forEach(([id, agent]) => {
      const agentElement = document.createElement('div');
      // Use list-group-item so it matches surrounding markup and is keyboard accessible
      agentElement.className = 'list-group-item d-flex align-items-center justify-content-between agent-item';
      agentElement.dataset.agentId = id;

      const statusClass = agent.is_available ? 'online' : 'busy';
      const name = `${agent.first_name || agent.name || ''} ${agent.last_name || ''}`.trim() || (agent.username || 'Agent');
      const sessionsCount = (typeof agent.active_sessions === 'number') ? agent.active_sessions : (agent.active_sessions || 0);

      agentElement.innerHTML = `
        <div class="d-flex align-items-center">
          <div class="agent-status-indicator me-2 ${statusClass}" aria-hidden="true"></div>
          <div class="agent-name">${name}</div>
        </div>
        <div class="agent-stats text-muted">${sessionsCount} chats</div>
      `;

      agentsList.appendChild(agentElement);
    });
  }
  
  renderCannedResponses() {
    const cannedSelect = document.getElementById('canned-responses-select');
    if (!cannedSelect) return;
    
    // Group responses by category
    const categories = {};
    this.cannedResponses.forEach(response => {
      const category = response.category || 'General';
      if (!categories[category]) {
        categories[category] = [];
      }
      categories[category].push(response);
    });
    
    // Clear existing options
    cannedSelect.innerHTML = '<option value="">Select a canned response...</option>';
    
    // Add options grouped by category
    Object.keys(categories).forEach(category => {
      const optGroup = document.createElement('optgroup');
      optGroup.label = category;
      
      categories[category].forEach(response => {
        const option = document.createElement('option');
        option.value = response.id;
        option.textContent = response.title;
        optGroup.appendChild(option);
      });
      
      cannedSelect.appendChild(optGroup);
    });
  }
  
  displayMessage(messageData) {
    // Note: Session reopening logic is now handled server-side in events.py
    // The server will emit session_updated events when a customer sends a message to a closed session
    
    // Create a unique identifier for the message to prevent duplicates
    const messageIdentifier = `${messageData.session_id}-${messageData.id || messageData.created_at}-${messageData.message}`;
    
    // Initialize the set for this session if it doesn't exist
    if (!this.displayedMessages.has(messageData.session_id)) {
      this.displayedMessages.set(messageData.session_id, new Set());
    }
    
    // Check if this message has already been displayed for this session
    if (this.displayedMessages.get(messageData.session_id).has(messageIdentifier)) {
      return; // Message already displayed for this session, don't show it again
    }
    
    // Add message to displayed messages set for this session
    this.displayedMessages.get(messageData.session_id).add(messageIdentifier);
    
    // Update session data with the latest message only if this is a full message object
    // with session_id, otherwise it's just a notification
    if (messageData.session_id && this.sessions[messageData.session_id]) {
      // Only update the last message if it's actually changed
      if (this.sessions[messageData.session_id].last_message !== messageData.message) {
        this.sessions[messageData.session_id].last_message = messageData.message;
        this.sessions[messageData.session_id].last_message_time = messageData.created_at;
        // Re-render session list to show updated last message
        this.renderChatSessions();
      }
    }
    
    // Get the messages container
    const messagesContainer = document.getElementById('chat-messages-container');
    
    // Display messages in the UI if we have a container
    if (!messagesContainer || !messageData.session_id) return;
    
    // Create message element for the main chat window (current session)
    if (messageData.session_id === this.currentSessionId) {
      const messageElement = document.createElement('div');
      
      // Determine message type
      const messageType = messageData.sender_type === 'agent' ? 'agent' :
                         messageData.sender_type === 'system' ? 'system' : 'customer';
      
      messageElement.className = `message ${messageType}`;
      // Include a delete button for admins (visible only to admin clients)
      const deleteControl = (this.isAdminClient ? `<button class="btn btn-sm btn-danger message-delete-btn" data-message-id="${messageData.id}" data-session-id="${messageData.session_id}" title="Delete message"><i class="fas fa-trash"></i></button>` : '');
      messageElement.innerHTML = `
        <div class="d-flex justify-content-between align-items-start">
          <div class="message-content">${this.formatMessageContent(messageData)}</div>
          <div class="ms-2">${deleteControl}</div>
        </div>
        <div class="message-time">
          ${this.formatTime(messageData.created_at)}
        </div>
      `;

      // Attach delete handler if running in admin client
      if (this.isAdminClient) {
        // Delegate click handler
        setTimeout(() => {
          const btn = messageElement.querySelector('.message-delete-btn');
          if (btn) {
            btn.addEventListener('click', (e) => {
              e.stopPropagation();
              const msgId = btn.getAttribute('data-message-id');
              const sessId = btn.getAttribute('data-session-id');
              if (confirm('Delete this message? This cannot be undone.')) {
                this.deleteMessage(sessId, msgId);
              }
            });
          }
        }, 0);
      }
      
      messagesContainer.appendChild(messageElement);
      this.scrollToBottom(messagesContainer);
    }
    
    // Show notice for new messages on first chat assigned only
    // Don't duplicate messages in all conversation lists
    const sessionElement = document.querySelector(`[data-session-id="${messageData.session_id}"]`);
    if (sessionElement) {
      // Only show notification for customer messages (not admin messages to avoid loops)
      if (messageData.sender_type === 'customer') {
        // Update the last message preview in the session list
        const lastMessageElement = sessionElement.querySelector('.session-last-message');
        if (lastMessageElement) {
          lastMessageElement.textContent = messageData.message;
        }
        
        // Update the time
        const timeElement = sessionElement.querySelector('.session-time');
        if (timeElement) {
          timeElement.textContent = this.formatTime(messageData.created_at);
        }
        
        // Add unread indicator if this is not the current session
        if (messageData.session_id !== this.currentSessionId) {
          const unreadBadge = sessionElement.querySelector('.session-unread-badge');
          if (unreadBadge) {
            // Increment the count
            const count = parseInt(unreadBadge.textContent) || 0;
            const newCount = count + 1;
            unreadBadge.textContent = newCount;
            // Sync model
            if (this.sessions && this.sessions[messageData.session_id]) {
              this.sessions[messageData.session_id].unread_count = newCount;
            }
          } else {
            // Create new unread badge
            const badgeContainer = sessionElement.querySelector('.d-flex.justify-content-between.align-items-center');
            if (badgeContainer) {
              const badge = document.createElement('span');
              badge.className = 'session-unread-badge me-2';
              badge.textContent = '1';
              // Insert before the delete button
              const deleteBtn = badgeContainer.querySelector('.delete-session-btn');
              if (deleteBtn) {
                badgeContainer.insertBefore(badge, deleteBtn);
              } else {
                badgeContainer.appendChild(badge);
              }
            }
            // Sync model
            if (this.sessions && this.sessions[messageData.session_id]) {
              this.sessions[messageData.session_id].unread_count = 1;
            }
          }

          // Show a notification for new messages
          this.showNotification({
            title: 'New Message',
            message: `New message from ${this.sessions[messageData.session_id]?.customer_name || 'Customer'}`
          });
          // Update overall session counts UI
          this.updateSessionCounts();
        }
      }
    }
  }
  
  formatMessageContent(messageData) {
    let content = messageData.message || '';
    
    // Handle attachments
    if (messageData.attachment_url) {
      if (messageData.message_type === 'image') {
        content += `<br><img src="${messageData.attachment_url}" class="message-attachment" alt="Attachment">`;
      } else {
        content += `<br><a href="${messageData.attachment_url}" target="_blank" class="message-attachment">
          <i class="fas fa-file"></i> ${this.getFileName(messageData.attachment_url)}
        </a>`;
      }
    }
    
    return content;
  }
  
  sendMessage() {
    const messageInput = document.getElementById('admin-message-input');
    const messageText = messageInput ? messageInput.value.trim() : '';
    const sendButton = document.getElementById('admin-send-btn');
    
    if (!this.currentSessionId) {
      // Reset button state
      if (sendButton) {
        sendButton.disabled = false;
        sendButton.innerHTML = '<i class="fas fa-paper-plane"></i> <span class="d-none d-md-inline ms-1">Send</span>';
      }
      return;
    }
    
    // Prevent sending if session is not active (unassigned/waiting sessions must be assigned first)
    const session = this.sessions[this.currentSessionId];
    if (!session || session.status !== 'active') {
      // Reset button state
      if (sendButton) {
        sendButton.disabled = false;
        sendButton.innerHTML = '<i class="fas fa-paper-plane"></i> <span class="d-none d-md-inline ms-1">Send</span>';
      }
      this.showNotification({ title: 'Not Assigned', message: 'This chat session must be assigned before sending messages.' });
      return;
    }

    if (messageText) {
      // Show processing state on button
      if (sendButton) {
        sendButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> <span class="d-none d-md-inline ms-1">Sending...</span>';
        sendButton.disabled = true;
      }
      
      // Don't display message immediately in UI to avoid duplication
      // The message will be displayed when received back from the server
      
      // Emit message to server
      this.socket.emit('send_message', {
        session_id: this.currentSessionId,
        message: messageText,
        attachment: this.getAttachmentData()
      });
      
      // Show popup notification when admin sends a message
      // this.showNotification({
      //   title: 'Message Sent',
      //   message: `Your message has been sent to the customer.`
      // });
      
      // Clear input
      if (messageInput) {
        messageInput.value = '';
      }
      
      // Clear attachment
      this.removeAttachment();
      
      // Reset button state after a short delay to ensure message is sent
      setTimeout(() => {
        if (sendButton) {
          sendButton.disabled = false;
          sendButton.innerHTML = '<i class="fas fa-paper-plane"></i> <span class="d-none d-md-inline ms-1">Send</span>';
        }
      }, 500);
    } else {
      // Reset button state if no message to send
      if (sendButton) {
        sendButton.disabled = false;
        sendButton.innerHTML = '<i class="fas fa-paper-plane"></i> <span class="d-none d-md-inline ms-1">Send</span>';
      }
    }
  }
  
  showCustomerTyping(data) {
    // Only show typing indicator for the current session (coerce types)
    if (String(data.session_id) !== String(this.currentSessionId)) return;

    const typingIndicator = document.getElementById('customer-typing-indicator');
    if (!typingIndicator) return;

    if (data.is_typing) {
      typingIndicator.classList.remove('d-none');
      // Update the text to show "Customer is typing..."
      const textElement = typingIndicator.querySelector('.text-muted');
      if (textElement) {
        textElement.textContent = 'Customer is typing...';
      }

      // Reset any previous hide timeout so repeated typing events keep the indicator visible
      if (this.customerTypingTimeout) {
        clearTimeout(this.customerTypingTimeout);
      }
      this.customerTypingTimeout = setTimeout(() => {
        typingIndicator.classList.add('d-none');
        this.customerTypingTimeout = null;
      }, 3000);
    } else {
      typingIndicator.classList.add('d-none');
      if (this.customerTypingTimeout) {
        clearTimeout(this.customerTypingTimeout);
        this.customerTypingTimeout = null;
      }
    }
  }
  
  updateSessionStatus(data) {
    // Update session in our data store
    if (this.sessions[data.session_id]) {
      const oldStatus = this.sessions[data.session_id].status;
      Object.assign(this.sessions[data.session_id], data);
      
      // Show notification if session was reopened from closed to waiting
      if (oldStatus === 'closed' && data.status === 'waiting') {
        this.showNotification({
          title: 'Session Reopened',
          message: `Customer sent a new message. Session #${data.session_id} is now waiting for assignment.`
        });
      }
    }

    // Ensure we join the session room when it becomes active or waiting so we receive
    // session-scoped events (typing, messages) even if the admin previously closed it.
    if (this.socket && (data.status === 'active' || data.status === 'waiting')) {
      try {
        this.socket.emit('join_session', {
          session_id: data.session_id,
          customer_name: this.sessions[data.session_id] ? this.sessions[data.session_id].customer_name : 'Customer',
          silent: true
        });
      } catch (e) {
        // ignore join errors
      }
    }

    // Update UI if this is the current session (coerce types)
    if (String(data.session_id) === String(this.currentSessionId)) {
      const chatStatus = document.getElementById('current-chat-status');
      if (chatStatus) {
        chatStatus.textContent = `Status: ${data.status} ${data.agent_name ? `| Assigned to ${data.agent_name}` : ''}`;
      }
      
      // Enable/disable action buttons and input group based on session status
  if (data.status === 'closed') {
        // If session is closed, disable both btn-group and input-group
        // They should remain disabled until customer sends a message
        this.disableActionButtons();
        this.disableInputGroup();

        // Clear displayed messages for this session
        this.clearDisplayedMessagesForSession(data.session_id);
      } else if (data.status === 'active') {
        // If session is active, enable the btn-group (actions).
        this.enableActionButtons();

        // Enable input group only if an agent has been assigned
        if (data.agent_id) {
          this.enableInputGroup();
        } else {
          this.disableInputGroup();
        }

        // Since session is active and assigned, disable the assign button specifically
        const assignBtn = document.getElementById('assign-chat-btn');
        if (assignBtn && data.agent_id) {
          assignBtn.disabled = true;
          assignBtn.classList.add('disabled');
          assignBtn.setAttribute('disabled', 'disabled');
        }
      } else if (data.status === 'waiting') {
        // For waiting sessions (customer sent a message after closure), enable only the btn-group
        // so admins can assign the session. Keep the input group disabled until assignment.
        // Ensure the btn-group is immediately visible and enabled (no page refresh needed).
        const btnGroup = document.querySelector('.btn-group[role="group"]');
        if (btnGroup) {
          btnGroup.style.display = 'flex';
          btnGroup.style.visibility = 'visible';
          btnGroup.classList.remove('d-none');
        }
        this.enableActionButtons();
        this.disableInputGroup();

        // Show additional notification if this is the current session
        if (data.message && data.message.toLowerCase().includes('reopen')) {
          this.showNotification({
            title: 'Current Session Waiting',
            message: 'Customer sent a new message. Assign the session to respond.'
          });
        }
      }
    }
    
    // Re-render session list
    this.renderChatSessions();
    this.updateSessionCounts();
  }
  
  updateAgentStatus(data) {
    // Update agent in our data store
    // Normalize incoming agent id
    const incomingId = String(data.agent_id || data.id || data.user_id);
    if (this.agents[incomingId]) {
      Object.assign(this.agents[incomingId], data);
    } else {
      // If agent doesn't exist yet, add a normalized entry
      this.agents[incomingId] = Object.assign({
        is_available: !!data.is_available,
        active_sessions: data.active_sessions || 0
      }, data, { id: incomingId });
    }
    
    // Re-render agents list
    this.renderAgents();
    this.updateAgentCounts();
  }
  
  addNewChatSession(data) {
    // Add to our sessions data
    this.sessions[data.session_id] = {
      id: data.session_id,
      customer_name: data.customer_name,
      last_message: data.message_preview,
      last_message_time: new Date().toISOString(),
      status: 'waiting',
      unread_count: 1
    };
    
    // Join the session room to receive real-time messages
    if (this.socket) {
      // Join silently to avoid notifying other participants that the admin auto-joined
      this.socket.emit('join_session', {
        session_id: data.session_id,
        customer_name: data.customer_name || 'Customer',
        silent: true
      });
    }
    
    // Always enable btn-group when customer joins new session for assignment
    // This ensures admins can immediately assign the new session
    if (this.currentSessionId === data.session_id) {
      this.enableActionButtons();
      this.disableInputGroup();
    } else {
      // For new sessions, ensure the button group is accessible
      this.disableActionButtons();
    }
    
    // Check if auto-assign is enabled
    const autoAssignToggle = document.getElementById('auto-assign-toggle');
    const isAutoAssignEnabled = autoAssignToggle && autoAssignToggle.checked;
    
    // If auto-assign is enabled, assign this session to the current admin
    if (isAutoAssignEnabled) {
      this.assignSessionToAdmin(data.session_id);
    }
    
    // Re-render session list
    this.renderChatSessions();
    this.updateSessionCounts();
    
    // Show notification
    this.showNotification({
      title: 'New Chat',
      message: `New chat from ${data.customer_name}`
    });
  }
  
  assignSessionToAdmin(sessionId) {
    // In a real implementation, this would make an API call to assign the session to the current admin
    
    // Update session status in our data store
    if (this.sessions[sessionId]) {
      this.sessions[sessionId].status = 'active';
      this.sessions[sessionId].agent_name = 'Current Admin'; // In a real implementation, this would be the actual admin name
    }
    
    // Emit event to update session status (in a real implementation, this would be done via API)
    this.socket.emit('session_updated', {
      session_id: sessionId,
      status: 'active',
      agent_name: 'Current Admin'
    });
    
    // Also emit to admins
    this.socket.emit('session_updated', {
      session_id: sessionId,
      status: 'active',
      agent_name: 'Current Admin'
    }, room='admins');
    
    // Re-render session list
    this.renderChatSessions();
    this.updateSessionCounts();
    
    // If no session is currently selected, automatically select this session
    if (!this.currentSessionId) {
      this.selectChatSession(sessionId);
    }
  }
  
  updateSessionCounts() {
    // Update active and waiting chat counts
    const activeCount = document.getElementById('active-chats-count');
    const waitingCount = document.getElementById('waiting-chats-count');
    
    if (activeCount || waitingCount) {
      let active = 0;
      let waiting = 0;
      
      Object.values(this.sessions).forEach(session => {
        if (session.status === 'active') {
          active++;
        } else if (session.status === 'waiting') {
          waiting++;
        }
      });
      
      if (activeCount) activeCount.textContent = active;
      if (waitingCount) waitingCount.textContent = waiting;
    }
  }
  
  updateAgentCounts() {
    // Update online agents count
    const onlineCount = document.getElementById('online-agents-count');
    
    if (onlineCount) {
      const online = Object.values(this.agents).filter(agent => agent.is_available).length;
      onlineCount.textContent = online;
    }
  }
  
  updateDashboardStats(data = {}) {
    // Update dashboard statistics
    const avgResponseTime = document.getElementById('avg-response-time');
    const resolutionRate = document.getElementById('resolution-rate');
    const todayChats = document.getElementById('today-chats');
    const customerSatisfaction = document.getElementById('customer-satisfaction');
    
    if (avgResponseTime) {
      avgResponseTime.textContent = data.avg_response_time ? `${Math.round(data.avg_response_time)}s` : '0s';
    }
    
    if (resolutionRate) {
      resolutionRate.textContent = data.resolution_rate ? `${Math.round(data.resolution_rate)}%` : '0%';
    }
    
    if (todayChats) {
      todayChats.textContent = data.today_chats || '0';
    }
    
    if (customerSatisfaction) {
      customerSatisfaction.textContent = data.customer_satisfaction ? `${Math.round(data.customer_satisfaction)}` : '0';
    }
  }
  
  toggleAutoAssign(enabled) {
    // In a real implementation, this would make an API call to update the setting
    
    // Provide visual feedback to the user
    const toggleElement = document.getElementById('auto-assign-toggle');
    if (toggleElement) {
      if (enabled) {
        // Show a success message
        this.showNotification({
          title: 'Auto-assign Enabled',
          message: 'New chats will be automatically assigned to available agents.'
        });
      } else {
        // Show a warning message
        this.showNotification({
          title: 'Auto-assign Disabled',
          message: 'New chats will need to be manually assigned to agents.'
        });
      }
    }
  }
  
  saveAutoAssignState(enabled) {
    // Save the auto-assign state to localStorage
    try {
      localStorage.setItem('adminAutoAssignEnabled', JSON.stringify(enabled));
    } catch (e) {
    }
  }
  
  loadAutoAssignState() {
    // Load the auto-assign state from localStorage
    try {
      const savedState = localStorage.getItem('adminAutoAssignEnabled');
      if (savedState !== null) {
        const enabled = JSON.parse(savedState);
        const toggleElement = document.getElementById('auto-assign-toggle');
        if (toggleElement) {
          toggleElement.checked = enabled;
        }
      }
    } catch (e) {
    }
  }
  
  filterChatSessions(filter) {
    // Filter rendered session DOM elements according to filter value
    this.currentFilter = filter || 'all';
    const sessionsList = document.getElementById('chat-sessions-list');
    if (!sessionsList) return;

    const items = sessionsList.querySelectorAll('.chat-session-item');
    items.forEach(item => {
      let visible = true;
      if (this.currentFilter === 'unassigned') {
        visible = !item.dataset.agentId || item.dataset.agentId === '';
      } else if (this.currentFilter === 'mine') {
        // Assigned to current admin
        visible = item.dataset.agentId && this.currentAdminId && String(item.dataset.agentId) === String(this.currentAdminId);
      } else if (this.currentFilter === 'high') {
        visible = item.dataset.priority && item.dataset.priority.toLowerCase() === 'high';
      } else {
        visible = true; // 'all' or unknown -> show all
      }

      if (visible) {
        item.style.display = '';
      } else {
        item.style.display = 'none';
      }
    });
  }

  applyFilterUI(filter) {
    // Update the dropdown button text to reflect current filter
    const dropdown = document.getElementById('filterDropdown');
    if (dropdown) {
      const labelMap = {
        'all': 'All Conversations',
        'unassigned': 'Unassigned',
        'mine': 'Assigned to Me',
        'high': 'High Priority'
      };
      dropdown.textContent = labelMap[filter] || 'Filter';
    }
    // visually mark active item in dropdown
    const dropdownItems = document.querySelectorAll('#filterDropdown + .dropdown-menu .dropdown-item');
    dropdownItems.forEach(it => {
      if (it.dataset.filter === filter) it.classList.add('active'); else it.classList.remove('active');
    });
  }
  
  transferChat() {
    if (!this.currentSessionId) {
      // Instead of alert, we could show a toast notification or similar
      return;
    }
    
    // In a real implementation, this would show a dialog to select an agent
    // and then make an API call to transfer the chat
  }
  
  assignChat() {
    if (!this.currentSessionId) {
      this.showNotification({
        title: 'Error',
        message: 'No chat session selected'
      });
      return;
    }
    
    // Get the session to check its current status
    const session = this.sessions[this.currentSessionId];
    if (!session) {
      this.showNotification({
        title: 'Error',
        message: 'Session not found'
      });
      return;
    }
    
    // Check if session is already assigned
    if (session.status === 'active' && session.agent_id) {
      this.showNotification({
        title: 'Info',
        message: 'Session already assigned to an agent'
      });
      return;
    }
    
    // Make API call to assign session to current admin
    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    fetch(`/messenger/api/sessions/${this.currentSessionId}/assign`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        // Update session data
        if (this.sessions[this.currentSessionId]) {
          this.sessions[this.currentSessionId].status = 'active';
          this.sessions[this.currentSessionId].agent_id = data.session.agent_id;
          this.sessions[this.currentSessionId].agent_name = data.session.agent_name;
          this.sessions[this.currentSessionId].assigned_at = data.session.assigned_at;
        }
        
        // Update UI
        this.updateSessionStatus({
          session_id: this.currentSessionId,
          status: 'active',
          agent_id: data.session.agent_id,
          agent_name: data.session.agent_name
        });
        
        // Show success notification
        this.showNotification({
          title: 'Success',
          message: 'Chat session assigned successfully'
        });
        
        // Enable action buttons
          this.enableActionButtons();
          // Enable input group now that session is assigned
          this.enableInputGroup();
          // Disable assign button to prevent re-assign
          const assignBtn = document.getElementById('assign-chat-btn');
          if (assignBtn) {
            assignBtn.disabled = true;
            assignBtn.classList.add('disabled');
            assignBtn.setAttribute('disabled', 'disabled');
          }
      } else {
        // Show error notification
        this.showNotification({
          title: 'Error',
          message: data.message || 'Failed to assign chat session'
        });
      }
    })
    .catch(error => {
      this.showNotification({
        title: 'Error',
        message: 'Failed to assign chat session: ' + error.message
      });
    });
  }
  
  closeChat() {
    if (!this.currentSessionId) {
      this.showNotification({
        title: 'Error',
        message: 'No chat session selected'
      });
      return;
    }
    
    // Show confirmation dialog using a custom approach since we don't have a built-in confirm dialog
    this.showNotification({
      title: 'Confirm Close',
      message: 'Are you sure you want to close this chat session? <button id="confirm-close-btn" class="btn btn-danger btn-sm mt-2">Yes, Close Chat</button>'
    });
    
    // Add event listener to the confirm button
    setTimeout(() => {
      const confirmBtn = document.getElementById('confirm-close-btn');
      if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
          // Remove the notification
          const toastContainer = document.getElementById('admin-toast-container');
          if (toastContainer) {
            toastContainer.innerHTML = '';
          }
          
          // Get CSRF token from meta tag
          const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
          
          fetch(`/messenger/api/sessions/${this.currentSessionId}/close`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken
            }
          })
          .then(response => {
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
          })
          .then(data => {
            if (data.success) {
              // Update session status
              if (this.sessions[this.currentSessionId]) {
                this.sessions[this.currentSessionId].status = 'closed';
              }
              
              // Clear saved session if it's the current session
                // Don't clear the saved session here. Mark it so the session_closed handler
                // knows not to clear the saved selection when the server emits the event.
                this.skipClearOnClose = this.currentSessionId;
              
              // Emit session closed event to session room and admins
              if (this.socket) {
                this.socket.emit('session_closed', {
                  session_id: this.currentSessionId,
                  message: 'This chat session has been closed by the support agent'
                }, `session_${this.currentSessionId}`);
              }
              
              // Update UI
              this.updateSessionStatus({ session_id: this.currentSessionId, status: 'closed' });
              
              // Show confirmation
              this.showNotification({
                title: 'Success',
                message: 'Chat session closed successfully'
              });
              
              // Clear current session ID to prevent further actions on closed session
              // Keep the session selected (do not null currentSessionId) so that when a customer
              // sends a new message and the server updates the session to 'waiting',
              // the btn-group can be re-enabled immediately without a page refresh.
              // However, visually disable inputs/actions for now.
              this.disableActionButtons();
              this.disableInputGroup();
            } else {
              this.showNotification({
                title: 'Error',
                message: 'Failed to close chat session: ' + data.message
              });
            }
          })
          .catch(error => {
            this.showNotification({
              title: 'Error',
              message: 'Failed to close chat session: ' + error.message
            });
          });
        });
      }
    }, 100);
  }
  
  deleteSession(sessionId) {
    if (confirm('Are you sure you want to delete this chat session? This action cannot be undone.')) {
      // Get CSRF token from meta tag
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
      
      fetch(`/messenger/api/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        }
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          // Remove session from our data store
          if (this.sessions[sessionId]) {
            delete this.sessions[sessionId];
          }
          
          // Clear saved session if it's the deleted session
          if (this.loadSelectedSession() == sessionId) {
            this.clearSelectedSession();
          }
          
          // If this was the current session, clear the UI
          if (this.currentSessionId === sessionId) {
            this.currentSessionId = null;
            this.updateSelectedSessionUI(null);
            const messagesContainer = document.getElementById('chat-messages-container');
            if (messagesContainer) {
              messagesContainer.innerHTML = `
                <div class="text-center text-muted d-flex align-items-center justify-content-center h-100" id="no-chat-selected">
                  <div>
                    <i class="fas fa-comment-alt fa-3x mb-3"></i>
                    <p>Select a conversation to start chatting</p>
                  </div>
                </div>
              `;
            }
            const contextPanel = document.getElementById('customer-context-panel');
            if (contextPanel) {
              contextPanel.innerHTML = `
                <div class="text-center text-muted" id="no-customer-selected">
                  <i class="fas fa-user fa-2x mb-2"></i>
                  <p>Select a conversation to view customer details</p>
                </div>
              `;
            }
            const transferBtn = document.getElementById('transfer-chat-btn');
            const closeBtn = document.getElementById('close-chat-btn');
            const assignBtn = document.getElementById('assign-chat-btn');
            if (transferBtn) {
              transferBtn.disabled = true;
              transferBtn.classList.add('disabled');
              transferBtn.setAttribute('disabled', 'disabled');
            }
            if (closeBtn) {
              closeBtn.disabled = true;
              closeBtn.classList.add('disabled');
              closeBtn.setAttribute('disabled', 'disabled');
            }
            if (assignBtn) {
              assignBtn.disabled = true;
              assignBtn.classList.add('disabled');
              assignBtn.setAttribute('disabled', 'disabled');
            }
          }
          
          // Notify the customer to clear their session and history
          if (this.socket) {
            this.socket.emit('clear_customer_session', { session_id: sessionId });
          }
          
          // Re-render session list
          this.renderChatSessions();
          this.updateSessionCounts();
          
          // Show confirmation
          alert('Chat session deleted successfully');
        } else {
          alert('Failed to delete chat session: ' + data.message);
        }
      })
      .catch(error => {
        alert('Failed to delete chat session');
      });
      
      // Clear displayed messages for this session
      this.clearDisplayedMessagesForSession(sessionId);
    }
  }
  
  insertCannedResponse(responseId) {
    // In a real implementation, this would fetch the response content
    // and insert it into the message input
  }
  
  openAttachmentDialog() {
    // Implementation for opening file dialog
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*,.pdf,.txt,.doc,.docx';
    input.onchange = (e) => {
      this.handleFileSelect(e.target.files[0]);
    };
    input.click();
  }
  
  handleFileSelect(file) {
    if (file) {
      // Validate file size (10MB limit)
      if (file.size > 10 * 1024 * 1024) {
        alert('File size exceeds 10MB limit');
        return;
      }
      
      // Show preview
      const preview = document.getElementById('admin-attachment-preview');
      const filename = document.getElementById('attachment-filename');
      if (!preview || !filename) return;
      
      preview.classList.remove('d-none');
      filename.textContent = file.name;
      
      // Store file data for sending
      this.currentAttachment = file;
    }
  }
  
  removeAttachment() {
    const preview = document.getElementById('admin-attachment-preview');
    if (preview) {
      preview.classList.add('d-none');
    }
    this.currentAttachment = null;
  }
  
  getAttachmentData() {
    // In a real implementation, this would return the attachment data
    // For now, we'll return null
    return null;
  }

  deleteMessage(sessionId, messageId) {
    // CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    fetch(`/messenger/api/sessions/${sessionId}/messages/${messageId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        // Remove message from UI if present
        const messagesContainer = document.getElementById('chat-messages-container');
        if (messagesContainer) {
          const msgBtn = messagesContainer.querySelector(`.message-delete-btn[data-message-id="${messageId}"]`);
          if (msgBtn) {
            const msgEl = msgBtn.closest('.message');
            if (msgEl && msgEl.parentNode) msgEl.parentNode.removeChild(msgEl);
          }
        }

        // Clear displayed messages cache for session so next load is fresh
        this.clearDisplayedMessagesForSession(sessionId);

        // Notify customer widgets to clear their saved messages/session
        if (this.socket) {
          this.socket.emit('clear_customer_session', { session_id: sessionId });
        }

        this.showNotification({ title: 'Message Deleted', message: 'Message deleted successfully' });
      } else {
        this.showNotification({ title: 'Error', message: data.message || 'Failed to delete message' });
      }
    })
    .catch(err => {
      this.showNotification({ title: 'Error', message: 'Failed to delete message' });
    });
  }
  
  handleTyping() {
    if (!this.currentSessionId) return;
    
    // Clear previous timeout
    if (this.typingTimeout) {
      clearTimeout(this.typingTimeout);
    }
    
    // If we weren't typing before, send typing start
    if (!this.isTyping) {
      this.isTyping = true;
      this.socket.emit('typing', {
        session_id: this.currentSessionId,
        is_typing: true
      });
    }
    
    // Set timeout to send typing stop
    this.typingTimeout = setTimeout(() => {
      this.isTyping = false;
      this.socket.emit('typing', {
        session_id: this.currentSessionId,
        is_typing: false
      });
    }, 1000);
  }
  
  scrollToBottom(container) {
    container.scrollTop = container.scrollHeight;
  }
  
  // Utility methods
  formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  
  formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString();
  }
  
  getFileName(url) {
    return url.split('/').pop();
  }
  
  showNotification(data) {
    // Show notification to admin
    if (data.message) {
      // Create a simple toast notification
      let toastContainer = document.getElementById('admin-toast-container');
      
      // If no container exists, create one
      if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'admin-toast-container';
        toastContainer.style.position = 'fixed';
        toastContainer.style.top = '20px';
        toastContainer.style.right = '20px';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
      }
      
      // Create toast element
      const toast = document.createElement('div');
      toast.className = 'admin-toast';
      toast.style.backgroundColor = '#333';
      toast.style.color = '#fff';
      toast.style.padding = '12px 20px';
      toast.style.borderRadius = '4px';
      toast.style.marginBottom = '10px';
      toast.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s';
      toast.style.maxWidth = '300px';
      
      toast.innerHTML = `
        <div style="font-weight: bold; margin-bottom: 5px;">${data.title || 'Notification'}</div>
        <div>${data.message}</div>
      `;
      
      toastContainer.appendChild(toast);
      
      // Show toast with fade-in effect
      setTimeout(() => {
        toast.style.opacity = '1';
      }, 10);
      
      // Remove toast after 5 seconds
      setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => {
          if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
          }
        }, 300);
      }, 5000);
    }
  }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  window.adminDashboard = new AdminDashboard();
});

// Helper function to clear displayed messages for a specific session
AdminDashboard.prototype.clearDisplayedMessagesForSession = function(sessionId) {
  // Clear displayed messages for this specific session
  if (this.displayedMessages.has(sessionId)) {
    this.displayedMessages.delete(sessionId);
  }
};
