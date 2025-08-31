// Customer Chat Widget JavaScript
class CustomerChatWidget {
  constructor() {
    this.socket = null;
    this.sessionId = null;
    this.isTyping = false;
    this.typingTimeout = null;
    this.widgetActive = false;
  // Track recent toasts to prevent duplicates when the same message
  // is emitted multiple times (e.g. server emits to both session and admins)
  this._recentToastIds = new Set();
    
    // Restore widget state if available
    const savedWidgetState = this.getSavedWidgetState();
    if (savedWidgetState !== null) {
      this.widgetActive = savedWidgetState;
    }
    
    this.initializeWidget();
    this.setupEventListeners();
    this.connectToSocket();
    
    // Restore chat messages if available
    this.restoreChatMessages();
    
    // If we're on the chat page, try to restore session
    if (window.location.pathname.includes('/messenger/chat')) {
      const savedSessionId = this.getSavedSessionId();
      if (savedSessionId) {
        this.sessionId = savedSessionId;
        // Join the session room immediately
        setTimeout(() => {
          if (this.socket) {
            this.socket.emit('join_session', {
              session_id: this.sessionId,
              customer_name: 'Customer'
            });
          }
        }, 100);
      }
    }
  }
  
  initializeWidget() {
    // Create widget elements if they don't exist
    if (!document.getElementById('chat-widget-container')) {
      this.createWidgetElements();
    }
    
    // Set initial state
    this.updateWidgetState();
  }
  
  createWidgetElements() {
    // Create the main container
    const container = document.createElement('div');
    container.id = 'chat-widget-container';
    container.className = 'chat-widget-container';
    container.innerHTML = `
      <button class="chat-widget-toggle" id="chat-widget-toggle">
        <i class="chat-widget-toggle-icon fas fa-comments"></i>
      </button>
      
      <div class="chat-widget" id="chat-widget">
        <div class="chat-widget-header">
          <h3 class="chat-widget-title">Customer Support</h3>
          <div class="chat-widget-header-status" id="chat-widget-header-status">
            <span class="agent-status-dot offline"></span>
            <span class="agent-status-text">Offline</span>
          </div>
          <div class="chat-widget-header-buttons">
            <button class="chat-widget-minimize" id="chat-widget-minimize">−</button>
            <button class="chat-widget-close" id="chat-widget-close">×</button>
          </div>
        </div>
        
        <div class="chat-widget-messages" id="chat-widget-messages">
          <div class="chat-message system">
            <div class="chat-message-content">Welcome to customer support! How can we help you today?</div>
            <div class="chat-message-time">${this.formatTime(new Date().toISOString())}</div>
          </div>
        </div>
        
        <div class="chat-widget-typing" id="chat-widget-typing">
          <div class="typing-indicator">
            <div class="typing-dots">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
            <span class="typing-text">Support is typing...</span>
          </div>
        </div>
        
        <div class="chat-widget-input-container">
          <input type="text" class="chat-widget-input" id="chat-widget-input" placeholder="Type your message...">
          <button class="chat-widget-send" id="chat-widget-send">
            <i class="fas fa-paper-plane"></i>
          </button>
        </div>
      </div>
    `;
    
    document.body.appendChild(container);
  }
  
  setupEventListeners() {
    // Toggle button
    const toggleBtn = document.getElementById('chat-widget-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        this.toggleWidget();
      });
    }
    
    // Minimize button
    const minimizeBtn = document.getElementById('chat-widget-minimize');
    if (minimizeBtn) {
      minimizeBtn.addEventListener('click', () => {
        this.minimizeWidget();
      });
    }
    
    // Close button
    const closeBtn = document.getElementById('chat-widget-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        this.closeSession();
      });
    }
    
    // Send button
    const sendBtn = document.getElementById('chat-widget-send');
    if (sendBtn) {
      sendBtn.addEventListener('click', () => {
        this.sendMessage();
      });
    }
    
    // Input field
    const inputField = document.getElementById('chat-widget-input');
    if (inputField) {
      inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          this.sendMessage();
        }
      });
      
      inputField.addEventListener('input', () => {
        this.handleTyping();
      });
    }
    
    // Close widget when clicking outside
    document.addEventListener('click', (e) => {
      const widget = document.getElementById('chat-widget');
      const toggle = document.getElementById('chat-widget-toggle');
      
      if (this.widgetActive && widget && toggle &&
          !widget.contains(e.target) && !toggle.contains(e.target)) {
        this.closeWidget();
      }
    });
  }
  
  connectToSocket() {
    // Connect to Socket.IO server
    this.socket = io();
    
    // Listen for events
    this.socket.on('connect', () => {
      
      // Ensure we join the saved session room if we have one so the widget
      // receives important server/admin events (like clear_customer_session)
      // even when minimized or not currently active.
      const savedSessionId = this.getSavedSessionId();
      const sessionToJoin = this.sessionId || savedSessionId;
      if (sessionToJoin) {
        try {
          this.socket.emit('join_session', {
            session_id: sessionToJoin,
            customer_name: 'Customer',
            silent: true
          });
        } catch (e) {
          // ignore join errors
        }
      }

      // Request agent status on connect
      this.socket.emit('get_agent_status');
    });
    
    this.socket.on('message_sent', (data) => {
      // Always display the message in the widget regardless of session ID
      // This ensures messages are displayed even before a session is established
      this.displayMessageInWidget(data);
      
      // Also display in main chat if we're on the chat page
      if (window.location.pathname.includes('/messenger/chat')) {
        this.displayMessageInMainChat(data);
      }
      
      // Show toast notification for new messages
      this.showNewMessageToast(data);
    });
    
    this.socket.on('agent_typing', (data) => {
      this.showAgentTyping(data);
    });
    
    this.socket.on('user_typing', (data) => {
      // Don't show anything when user is typing in customer interface
      // The typing indicator is shown in the admin interface
    });
    
    this.socket.on('agent_joined', (data) => {
      this.showAgentJoined(data);
    });

    // New: handle explicit session assigned event so customer sees agent assignment
    this.socket.on('session_assigned', (data) => {
      try {
        // Update in-memory session info if needed
        if (!this.sessionId && data.session_id) {
          this.sessionId = data.session_id;
          this.saveSessionId(this.sessionId);
        }

        // Show a system message that an agent joined/was assigned
        this.displayMessage({
          session_id: this.sessionId,
          message: data.message || `${data.agent_name} has been assigned to your chat.`,
          sender_type: 'system',
          created_at: new Date().toISOString()
        });

        // Update agent status UI
        this.updateAgentStatus(true);
        const agentNameEl = document.getElementById('agent-name');
        if (agentNameEl && data.agent_name) {
          agentNameEl.textContent = data.agent_name;
        }
      } catch (e) {
        // ignore errors
      }
    });
    
    this.socket.on('session_closed', (data) => {
      this.showSessionClosed(data);
    });
    
    this.socket.on('connect_error', (error) => {
    });
    
    this.socket.on('disconnect', (reason) => {
    });
    
    // Listen for agent status updates
    this.socket.on('agent_status', (data) => {
      this.updateAgentStatus(data && data.online);
    });

    // Listen for agent online/offline events (if available)
    this.socket.on('agent_online', () => {
      this.updateAgentStatus(true);
    });
    this.socket.on('agent_offline', () => {
      this.updateAgentStatus(false);
    });
    
    this.socket.on('clear_customer_session', (data) => {
      // Always clear persisted session and messages when server/admin emits
      // clear_customer_session. This prevents a situation where repeated admin
      // deletes only take effect once because the client's in-memory state was
      // already reset.
      try {
        this.clearSavedSessionId();
        this.clearSavedChatMessages();
      } catch (e) {
        // ignore localStorage errors
      }

      // Reset in-memory session id
      this.sessionId = null;

      // Replace widget messages with a system notice to reflect admin action
      const widgetMessagesContainer = document.getElementById('chat-widget-messages');
      if (widgetMessagesContainer) {
        widgetMessagesContainer.innerHTML = `
          <div class="chat-message system">
            <div class="chat-message-content">Your chat session has been cleared by the admin.</div>
            <div class="chat-message-time">${this.formatTime(new Date().toISOString())}</div>
          </div>
        `;
      }

      // Ensure widget is not left in an open/active state for the cleared session
      this.widgetActive = false;
      this.saveWidgetState(this.widgetActive);
      this.updateWidgetState();
    });
  }
  
  createChatSession(messageText = null) {
    // Check if we have a saved session ID
    const savedSessionId = this.getSavedSessionId();
    if (savedSessionId) {
      this.sessionId = savedSessionId;
      
      // Join the session room
      if (this.socket) {
        this.socket.emit('join_session', {
          session_id: this.sessionId,
          customer_name: 'Customer'
        });
        
      }
      
      // Send the message if provided
      if (messageText) {
        // Clear widget input if it exists
        const inputField = document.getElementById('chat-widget-input');
        if (inputField) {
          inputField.value = '';
        }
        
        // Emit message to server
        if (this.socket) {
          this.socket.emit('send_message', {
            session_id: this.sessionId,
            message: messageText
          });
        }
      }
      
      return Promise.resolve();
    }
    
    // Make an API call to create a session
    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    return fetch('/messenger/api/session', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          this.sessionId = data.session_id;
          
          // Save session ID
          this.saveSessionId(this.sessionId);
          
          // Join the session room
          if (this.socket) {
            this.socket.emit('join_session', {
              session_id: this.sessionId,
              customer_name: 'Customer'
            });
            
          }
          
          // Send the message if provided
          if (messageText) {
            // Clear widget input if it exists
            const inputField = document.getElementById('chat-widget-input');
            if (inputField) {
              inputField.value = '';
            }
            
            // Emit message to server
            if (this.socket) {
              this.socket.emit('send_message', {
                session_id: this.sessionId,
                message: messageText
              });
            }
          }
          
          return data;
        } else {
          throw new Error(data.message);
        }
      })
      .catch(error => {
        throw error;
      });
  }
  
  toggleWidget() {
    this.widgetActive = !this.widgetActive;
    this.saveWidgetState(this.widgetActive);
    this.updateWidgetState();

    // Scroll to bottom when opening
    if (this.widgetActive) {
      const messagesContainer = document.getElementById('chat-widget-messages');
      if (messagesContainer) {
        this.scrollToBottom(messagesContainer);
      }

      // Join the session room only when the widget is opened
      if (this.sessionId && this.socket) {
        this.socket.emit('join_session', {
          session_id: this.sessionId,
          customer_name: 'Customer'
        });
      }
    }
  }
  
  minimizeWidget() {
    this.widgetActive = false;
    this.saveWidgetState(this.widgetActive);
    this.updateWidgetState();
  }
  
  closeWidget() {
    this.widgetActive = false;
    this.saveWidgetState(this.widgetActive);
    this.updateWidgetState();
  }
  
  restoreChatMessages() {
    const savedMessages = this.getSavedChatMessages();
    const widgetMessagesContainer = document.getElementById('chat-widget-messages');
    
    if (widgetMessagesContainer && savedMessages.length > 0) {
      // Clear existing messages except the welcome message
      const welcomeMessage = widgetMessagesContainer.querySelector('.chat-message.system');
      widgetMessagesContainer.innerHTML = '';
      
      // Add back the welcome message if it existed
      if (welcomeMessage) {
        widgetMessagesContainer.appendChild(welcomeMessage);
      }
      
      // Add saved messages
      savedMessages.forEach(messageData => {
        this.displayMessageInWidget(messageData, false); // false to prevent saving again
      });
      
      // Scroll to bottom
      this.scrollToBottom(widgetMessagesContainer);
    }
  }
  
  closeSession() {
    // Close the session by emitting a close event to the server
    if (this.sessionId) {
      this.socket.emit('close_session', {
        session_id: this.sessionId
      });
      
      // Send notice to admin that customer has closed the conversation
      this.socket.emit('customer_left', {
        session_id: this.sessionId
      });
      
      // Clear saved session ID
      this.clearSavedSessionId();
    }
    
    // Close the widget
    this.closeWidget();
  }
  
  updateWidgetState() {
    const widget = document.getElementById('chat-widget');
    const toggle = document.getElementById('chat-widget-toggle');
    
    if (widget) {
      if (this.widgetActive) {
        widget.classList.add('active');
      } else {
        widget.classList.remove('active');
      }
    }
    
    // Update toggle icon
    const icon = toggle ? toggle.querySelector('.chat-widget-toggle-icon') : null;
    if (icon) {
      icon.className = 'chat-widget-toggle-icon fas ' + (this.widgetActive ? 'fa-times' : 'fa-comments');
    }
  }
  
  sendMessage(messageText = null) {
    // If no message text provided, get it from the widget input field
    if (!messageText) {
      const inputField = document.getElementById('chat-widget-input');
      messageText = inputField ? inputField.value.trim() : '';
    }

    if (!messageText) return;

    // If we don't have a session ID or the session was closed, create a new session first and send the message (only once)
    if (!this.sessionId) {
      this.createChatSession(messageText)
        .catch((error) => {
          // Show error to user
          this.displayMessage({
            session_id: null,
            message: 'Failed to start chat session. Please try again.',
            sender_type: 'system',
            created_at: new Date().toISOString()
          });
        });
      // Do not emit send_message again here; createChatSession will handle it
      return;
    }

    // Clear widget input if it exists
    const inputField = document.getElementById('chat-widget-input');
    if (inputField) {
      inputField.value = '';
    }

    // Emit session join event if the session was previously closed
    if (this.socket && !this.widgetActive) {
      this.socket.emit('join_session', {
        session_id: this.sessionId,
        customer_name: 'Customer'
      });
    }

    // Emit message to server
    if (this.socket) {
      this.socket.emit('send_message', {
        session_id: this.sessionId,
        message: messageText
      });
      // Stop typing indicator
      this.stopTyping();
    } else {
      this.displayMessage({
        session_id: this.sessionId,
        message: 'Failed to send message. Please check your connection and try again.',
        sender_type: 'system',
        created_at: new Date().toISOString()
      });
    }
  }
  
  // Method to send message from main chat page
  sendMessageFromMainChat(messageText) {
    // Use the same sendMessage method but with provided text
    this.sendMessage(messageText);
  }
  
  displayMessage(messageData) {
    // If we don't have a session ID yet, but we're receiving a message,
    // it means we're joining an existing session
    if (!this.sessionId && messageData.session_id) {
      this.sessionId = messageData.session_id;
      // Save the session ID
      this.saveSessionId(this.sessionId);
      // Join the session room
      if (this.socket) {
        this.socket.emit('join_session', {
          session_id: this.sessionId,
          customer_name: 'Customer'
        });
      }
    }
    
    // Check if we're on the chat page
    const onChatPage = window.location.pathname.includes('/messenger/chat');
    
    // If we're on the chat page, display in both main chat and widget
    if (onChatPage) {
      this.displayMessageInMainChat(messageData);
      // Also display in widget if it exists
      this.displayMessageInWidget(messageData);
      return;
    }
    
    // Otherwise, display in chat widget if it exists
    // Always display messages in the widget if we're not on the chat page
    this.displayMessageInWidget(messageData);
  }
  
  displayMessageInWidget(messageData, shouldSave = true) {
    const widgetMessagesContainer = document.getElementById('chat-widget-messages');
    if (widgetMessagesContainer) {
      // Create a unique identifier for the message
      const messageIdentifier = `${messageData.message}-${messageData.created_at}`;
      
      // Check if this message is already displayed to avoid duplication
      const existingMessages = widgetMessagesContainer.querySelectorAll('.chat-message');
      for (let i = 0; i < existingMessages.length; i++) {
        const existingMessage = existingMessages[i];
        const contentElement = existingMessage.querySelector('.chat-message-content');
        const timeElement = existingMessage.querySelector('.chat-message-time');
        
        if (contentElement && timeElement) {
          // Create identifier for existing message
          const existingIdentifier = `${contentElement.textContent}-${timeElement.textContent}`;
          if (existingIdentifier === messageIdentifier) {
            // Message already exists, don't display it again
            return;
          }
        }
      }
      
      const messageElement = document.createElement('div');
      
      // Determine message type
      const messageType = messageData.sender_type === 'agent' ? 'agent' :
                         messageData.sender_type === 'system' ? 'system' : 'customer';
      
      messageElement.className = `chat-message ${messageType}`;
      messageElement.innerHTML = `
        <div class="chat-message-content">${this.escapeHtml(messageData.message)}</div>
        <div class="chat-message-time">${this.formatTime(messageData.created_at)}</div>
      `;
      
      widgetMessagesContainer.appendChild(messageElement);
      this.scrollToBottom(widgetMessagesContainer);
      
      // Save messages to localStorage if shouldSave is true
      if (shouldSave) {
        // Get existing saved messages
        const savedMessages = this.getSavedChatMessages();
        
        // Add the new message
        savedMessages.push(messageData);
        
        // Keep only the last 100 messages to prevent localStorage from getting too large
        if (savedMessages.length > 100) {
          savedMessages.shift();
        }
        
        // Save updated messages
        this.saveChatMessages(savedMessages);
      }
    }
  }
  
  displayMessageInMainChat(messageData) {
    // Check if we're on the chat page by looking for the main messages container
    const mainMessagesContainer = document.getElementById('customer-messages-container');
    if (!mainMessagesContainer) return;
    
    // Remove the "no chat history" placeholder if it exists
    const noChatHistoryElement = document.getElementById('no-chat-history');
    if (noChatHistoryElement) {
      noChatHistoryElement.remove();
    }
    
    // Create message element for main chat
    const messageElement = document.createElement('div');
    
    // Determine message type
    const messageType = messageData.sender_type === 'agent' ? 'agent' :
                       messageData.sender_type === 'system' ? 'system' : 'customer';
    
    // Set appropriate classes for main chat display
    if (messageType === 'customer') {
      messageElement.className = 'alert alert-info';
    } else if (messageType === 'agent') {
      messageElement.className = 'alert alert-success';
    } else {
      messageElement.className = 'alert alert-secondary text-center';
    }
    
    // Format time for display
    const formattedTime = this.formatTime(messageData.created_at);
    
    messageElement.innerHTML = `
      <div class="d-flex justify-content-between align-items-center mb-1">
        <strong class="me-2">${messageType === 'customer' ? 'You' : messageType === 'agent' ? 'Support Agent' : 'System'}</strong>
        <small class="text-muted">${formattedTime}</small>
      </div>
      <div class="message-content">${this.escapeHtml(messageData.message)}</div>
    `;
    
    mainMessagesContainer.appendChild(messageElement);
    
    // Scroll to bottom of main chat container
    mainMessagesContainer.scrollTop = mainMessagesContainer.scrollHeight;
    
    // Also update chat status information
    const chatStatus = document.getElementById('chat-status');
    const agentName = document.getElementById('agent-name');
    const chatSubject = document.getElementById('chat-subject');
    const chatStarted = document.getElementById('chat-started');
    
    if (chatStatus) {
      chatStatus.textContent = 'Active';
    }
    
    // If this is an agent message, update agent name
    if (messageType === 'agent' && agentName) {
      // Extract agent name from message data if available
      if (messageData.sender_name && messageData.sender_name !== 'Customer') {
        agentName.textContent = messageData.sender_name;
      }
    }
    
    // Update chat subject if needed
    if (chatSubject && messageData.subject) {
      chatSubject.textContent = messageData.subject;
    }
    
    // Update chat start time if this is the first message
    if (chatStarted && !chatStarted.textContent || chatStarted.textContent === '-') {
      const messageDate = new Date(messageData.created_at);
      chatStarted.textContent = messageDate.toLocaleString();
    }
  }
  
  showAgentTyping(data) {
    // Only show typing indicator for the current session.
    // Use the active sessionId or fall back to saved session id (saved in localStorage)
    // This allows showing agent typing when the admin closed the session remotely
    // and the client-side `this.sessionId` was reset, but the saved session id still
    // matches the server session.
    const currentSessionId = this.sessionId || this.getSavedSessionId();
    if (String(data.session_id) !== String(currentSessionId)) return;
    
    // Show typing indicator in chat widget
    const widgetTypingIndicator = document.getElementById('chat-widget-typing');
    if (widgetTypingIndicator) {
      if (data.is_typing) {
        widgetTypingIndicator.classList.add('active');
        // Hide after delay
        setTimeout(() => {
          widgetTypingIndicator.classList.remove('active');
        }, 3000);
      } else {
        widgetTypingIndicator.classList.remove('active');
      }
    }
    
    // Show typing indicator in main chat page
    const mainTypingIndicator = document.getElementById('agent-typing-indicator');
    if (mainTypingIndicator) {
      if (data.is_typing) {
        mainTypingIndicator.classList.remove('d-none');
        // Hide after delay
        setTimeout(() => {
          mainTypingIndicator.classList.add('d-none');
        }, 3000);
      } else {
        mainTypingIndicator.classList.add('d-none');
      }
    }
  }
  
  showAgentJoined(data) {
    // Only show for the current session
    if (data.session_id !== this.sessionId) return;
    
    this.displayMessage({
      session_id: this.sessionId,
      message: `${data.agent_name} has joined the chat`,
      sender_type: 'system',
      created_at: new Date().toISOString()
    });
  }
  
  showSessionClosed(data) {
    // Only show for the current session
    // Coerce both sides to string to avoid int/string mismatch from server vs localStorage
    if (String(data.session_id) !== String(this.sessionId)) return;
    
    this.displayMessage({
      session_id: this.sessionId,
      message: data.message || 'This chat session has been closed',
      sender_type: 'system',
      created_at: new Date().toISOString()
    });
    
    // Reset session ID so a new session can be created
    this.sessionId = null;
    
    // Enable input field and send button for new session
    const inputField = document.getElementById('chat-widget-input');
    const sendBtn = document.getElementById('chat-widget-send');
    if (inputField) inputField.disabled = false;
    if (sendBtn) sendBtn.disabled = false;
  }
  
  updateAgentStatus(isOnline) {
    const statusContainer = document.getElementById('chat-widget-header-status');
    if (statusContainer) {
      const dot = statusContainer.querySelector('.agent-status-dot');
      const text = statusContainer.querySelector('.agent-status-text');
      if (dot && text) {
        if (isOnline) {
          dot.classList.remove('offline');
          dot.classList.add('online');
          text.textContent = 'Online';
        } else {
          dot.classList.remove('online');
          dot.classList.add('offline');
          text.textContent = 'Offline';
        }
      }
    }
  }
  
  handleTyping() {
    if (!this.sessionId) return;
    
    // Clear previous timeout
    if (this.typingTimeout) {
      clearTimeout(this.typingTimeout);
    }
    
    // If we weren't typing before, send typing start
    if (!this.isTyping) {
      this.isTyping = true;
      this.socket.emit('typing', {
        session_id: this.sessionId,
        is_typing: true
      });
    }
    
    // Set timeout to send typing stop
    this.typingTimeout = setTimeout(() => {
      this.stopTyping();
    }, 1000);
  }
  
  stopTyping() {
    if (this.isTyping && this.sessionId) {
      this.isTyping = false;
      this.socket.emit('typing', {
        session_id: this.sessionId,
        is_typing: false
      });
    }
  }
  
  scrollToBottom(container) {
    container.scrollTop = container.scrollHeight;
  }
  
  // Utility methods
  formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  // Session persistence methods
  saveSessionId(sessionId) {
    try {
      localStorage.setItem('customerChatSessionId', sessionId);
    } catch (e) {
    }
  }
  
  getSavedSessionId() {
    try {
      return localStorage.getItem('customerChatSessionId');
    } catch (e) {
      return null;
    }
  }
  
  clearSavedSessionId() {
    try {
      localStorage.removeItem('customerChatSessionId');
    } catch (e) {
    }
  }
// Widget state persistence methods
  saveWidgetState(isActive) {
    try {
      localStorage.setItem('customerChatWidgetActive', JSON.stringify(isActive));
    } catch (e) {
      // Silently fail if localStorage is not available
    }
  }
  
  getSavedWidgetState() {
    try {
      const savedState = localStorage.getItem('customerChatWidgetActive');
      return savedState ? JSON.parse(savedState) : null;
    } catch (e) {
      return null;
    }
  }
  
  // Chat messages persistence methods
  saveChatMessages(messages) {
    try {
      localStorage.setItem('customerChatMessages', JSON.stringify(messages));
    } catch (e) {
      // Silently fail if localStorage is not available
    }
  }
  
  getSavedChatMessages() {
    try {
      const savedMessages = localStorage.getItem('customerChatMessages');
      return savedMessages ? JSON.parse(savedMessages) : [];
    } catch (e) {
      return [];
    }
  }
  
  clearSavedChatMessages() {
    try {
      localStorage.removeItem('customerChatMessages');
    } catch (e) {
      // Silently fail if localStorage is not available
    }
  }
  
  // Simple toast for new messages (prevents missing function errors)
  showNewMessageToast(data) {
    try {
      // Deduplicate toasts. Use server-provided message id if present,
      // otherwise fall back to message text + timestamp.
      try {
        let toastKey = null;
        if (data && data.id) {
          toastKey = `id:${data.id}`;
        } else if (data && data.message && data.created_at) {
          toastKey = `msg:${data.message}-${data.created_at}`;
        }

        if (toastKey) {
          if (this._recentToastIds.has(toastKey)) {
            return; // duplicate
          }
          this._recentToastIds.add(toastKey);
          // Keep key for a short period slightly longer than toast display
          setTimeout(() => { this._recentToastIds.delete(toastKey); }, 4500);
        }
      } catch (e) {
        // if dedupe logic fails, continue to show toast
      }

      let container = document.getElementById('customer-chat-toast-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'customer-chat-toast-container';
        container.style.position = 'fixed';
        container.style.bottom = '100px';
        container.style.right = '20px';
        container.style.zIndex = '10001';
        document.body.appendChild(container);
      }

      const toast = document.createElement('div');
      toast.className = 'customer-chat-toast';
      toast.style.background = 'rgba(0,0,0,0.8)';
      toast.style.color = '#fff';
      toast.style.padding = '8px 12px';
      toast.style.borderRadius = '6px';
      toast.style.marginTop = '8px';
      toast.style.maxWidth = '280px';
      toast.style.fontSize = '13px';
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.25s ease';

      const sender = data && data.sender_type === 'agent' ? 'Support' : 'You';
      const messageText = data && data.message ? data.message : '';
      toast.innerHTML = `<strong style="display:block;margin-bottom:4px">${sender}</strong><div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${this.escapeHtml(messageText)}</div>`;

      container.appendChild(toast);

      // Fade in
      setTimeout(() => { toast.style.opacity = '1'; }, 10);

      // Auto remove after 3.5s
      setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 250);
      }, 3500);
    } catch (e) {
      // Silently ignore toast errors so they don't break message flow
    }
  }
}

// Initialize widget when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  // Check if we're on an admin page, if so don't initialize the widget
  if (window.location.pathname.includes('/admin') || window.location.pathname.includes('/messenger/admin')) {
    return;
  }
  
  // Check if Font Awesome is loaded, if not load it
  if (!document.querySelector('link[href*="fontawesome"]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css';
    document.head.appendChild(link);
  }
  
  // Initialize the widget
  window.customerChatWidget = new CustomerChatWidget();
  
  // Set up main chat page integration if we're on the chat page
  if (window.location.pathname.includes('/messenger/chat')) {
    // Initialize session if we have a saved session ID
    const savedSessionId = window.customerChatWidget.getSavedSessionId();
    if (savedSessionId) {
      window.customerChatWidget.sessionId = savedSessionId;
      // Join the session room
      setTimeout(() => {
        if (window.customerChatWidget.socket) {
          window.customerChatWidget.socket.emit('join_session', {
            session_id: savedSessionId,
            customer_name: 'Customer'
          });
        }
      }, 100);
    }
    setupMainChatIntegration();
  }
});

// Set up integration with main chat page
function setupMainChatIntegration() {
  // Set up event listener for main chat form submission
  const mainChatForm = document.getElementById('customer-message-form');
  if (mainChatForm) {
    mainChatForm.addEventListener('submit', function(e) {
      e.preventDefault();
      
      const messageInput = document.getElementById('customer-message-input');
      if (messageInput && messageInput.value.trim()) {
        window.customerChatWidget.sendMessageFromMainChat(messageInput.value.trim());
        messageInput.value = ''; // Clear input
      }
    });
  }
  
  // Set up event listener for Enter key in main chat input
  const mainMessageInput = document.getElementById('customer-message-input');
  if (mainMessageInput) {
    mainMessageInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        
        if (mainMessageInput.value.trim()) {
          window.customerChatWidget.sendMessageFromMainChat(mainMessageInput.value.trim());
          mainMessageInput.value = ''; // Clear input
        }
      }
    });
  }
}

// Add minimal CSS for status dot (inject if not present)
document.addEventListener('DOMContentLoaded', () => {
  // Inject CSS only if it doesn't exist
  if (!document.getElementById('customer-chat-widget-status-style')) {
    const style = document.createElement('style');
    style.id = 'customer-chat-widget-status-style';
    style.innerHTML = `
      .agent-status-dot {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 6px;
        vertical-align: middle;
        background: #bbb;
      }
      .agent-status-dot.online {
        background: #28a745;
      }
      .agent-status-dot.offline {
        background: #bbb;
      }
      .chat-widget-header-status {
        display: inline-flex;
        align-items: center;
        margin-left: 12px;
        font-size: 13px;
      }
    `;
    document.head.appendChild(style);
  }
});