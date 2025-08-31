// Admin Notifications JavaScript
// This file handles real-time notifications for admin users

document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on an admin page and user data is available
    const currentUserDataElement = document.getElementById('currentUserData');
    if (!currentUserDataElement) {
        console.log('Not on admin page or user data not available');
        return;
    }

    const currentUserData = JSON.parse(currentUserDataElement.textContent);
    if (!currentUserData.is_admin) {
        console.log('Current user is not an admin');
        return;
    }

    // Initialize Socket.IO connection
    const socket = io();

    // Listen for new message notifications
    socket.on('new_message_notification', function(data) {
        console.log('New message notification received:', data);
        
        // Update notification badge
        const notificationBadge = document.getElementById('navNotificationBadge');
        if (notificationBadge) {
            const currentCount = parseInt(notificationBadge.textContent) || 0;
            notificationBadge.textContent = currentCount + 1;
            notificationBadge.style.display = 'inline-block';
        }

        // Show browser notification if supported
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('New Support Message', {
                body: `From: ${data.sender_name}\nMessage: ${data.message.substring(0, 50)}...`,
                icon: '/static/images/notification-icon.png'
            });
        }
    });

    // Listen for chat session assigned notifications
    socket.on('chat_session_assigned', function(data) {
        console.log('Chat session assigned notification received:', data);
        
        // Show a toast or alert to the admin
        alert(`New chat session assigned to you: ${data.session_id}\nCustomer: ${data.customer_name}`);
    });

    // Backwards-compatible listener for session_assigned
    socket.on('session_assigned', function(data) {
        console.log('session_assigned received:', data);
        alert(`Chat session ${data.session_id} has been assigned to ${data.agent_name}`);
    });

    // Request notification permission
    if ('Notification' in window) {
        Notification.requestPermission().then(function(permission) {
            if (permission === 'granted') {
                console.log('Notification permission granted.');
            }
        });
    }
});