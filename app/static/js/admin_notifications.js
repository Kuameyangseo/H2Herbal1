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

    // When connected, explicitly join the 'admins' room so server emits to
    // room='admins' reach this client even if server-side auto-join fails.
    socket.on('connect', function() {
        try {
            socket.emit('join_room', { room: 'admins' });
            console.log('Admin socket connected and requested to join admins room');
        } catch (e) {
            console.error('Failed to join admins room on connect', e);
        }
    });

    // Listen for admin_notification (server-side emits this for alerts)
    socket.on('admin_notification', function(data) {
        console.log('admin_notification received:', data);

        // Update notification badge
        const notificationBadge = document.getElementById('navNotificationBadge');
        if (notificationBadge) {
            const currentCount = parseInt(notificationBadge.textContent) || 0;
            notificationBadge.textContent = currentCount + 1;
            notificationBadge.style.display = 'inline-block';
        }

        // Optionally show browser notification if supported
        if ('Notification' in window && Notification.permission === 'granted') {
            const messageText = data.message ? (data.message.substring(0, 50) + (data.message.length > 50 ? '...' : '')) : '';
            new Notification(data.title || 'Support Notification', {
                body: messageText,
                icon: '/static/images/notification-icon.png'
            });
        }
    });

    // Also listen for message_sent so admin dashboards can react to actual messages
    socket.on('message_sent', function(data) {
        console.log('message_sent received for admin:', data);

        // Update notification badge as a lightweight notification
        const notificationBadge = document.getElementById('navNotificationBadge');
        if (notificationBadge) {
            const currentCount = parseInt(notificationBadge.textContent) || 0;
            notificationBadge.textContent = currentCount + 1;
            notificationBadge.style.display = 'inline-block';
        }

        // You may add UI logic here to insert the message into the admin messages list
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