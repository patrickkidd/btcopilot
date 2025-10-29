/**
 * User Detail Component JavaScript
 * Comprehensive functionality for user detail modal, user table management, and role editing
 * Works in both admin and auditor contexts
 */

// User Detail Modal Functions
function showUserDetailModal(userId) {
    // Load user details as HTML
    fetch(`/training/admin/users/${userId}/detail-html`, {
        credentials: 'same-origin'
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.text();
        })
        .then(html => {
            // Update modal title
            document.getElementById('userDetailTitle').textContent = `User Details`;
            
            // Replace modal content with server-rendered HTML
            const contentDiv = document.getElementById('userDetailContent');
            contentDiv.innerHTML = html;
            
            // Show the modal
            document.getElementById('userDetailModal').classList.add('is-active');
        })
        .catch(error => {
            console.error('Error loading user details:', error);
            alert('Failed to load user details: ' + error.message);
        });
}

function hideUserDetailModal() {
    document.getElementById('userDetailModal').classList.remove('is-active');
}

// Edit roles functionality - works in both modal and embedded contexts
function startEditRoles() {
    const displayDiv = document.getElementById('detail-roles-display');
    const editDiv = document.getElementById('detail-roles-edit');
    
    if (displayDiv && editDiv) {
        displayDiv.style.display = 'none';
        editDiv.style.display = 'block';
    }
}

function cancelEditRoles() {
    const displayDiv = document.getElementById('detail-roles-display');
    const editDiv = document.getElementById('detail-roles-edit');
    
    if (displayDiv && editDiv) {
        displayDiv.style.display = 'block';
        editDiv.style.display = 'none';
    }
}

function saveUserRoles() {
    // Get the user ID from the context (modal or embedded)
    let userId = null;
    let userInfoBox = null;
    
    // First try to find in modal content
    const userDetailContent = document.getElementById('userDetailContent');
    if (userDetailContent) {
        userInfoBox = userDetailContent.querySelector('[data-user-id]');
    }
    
    // If not in modal, try to find in the main page
    if (!userInfoBox) {
        userInfoBox = document.querySelector('[data-user-id]');
    }
    
    if (userInfoBox) {
        userId = userInfoBox.getAttribute('data-user-id');
    }

    if (!userId) {
        alert('Unable to determine user ID. Please refresh the page and try again.');
        return;
    }

    // Get selected roles from checkboxes
    const roles = [];
    const checkboxes = ['role-subscriber', 'role-admin', 'role-auditor'];
    
    for (const checkboxId of checkboxes) {
        const checkbox = document.getElementById(checkboxId);
        if (checkbox && checkbox.checked) {
            roles.push(checkbox.value);
        }
    }

    // Find the save button (could be the event target or find it in DOM)
    let saveButton = null;
    if (typeof event !== 'undefined' && event.target) {
        saveButton = event.target;
    } else {
        // Fallback: find the save button in the current context
        saveButton = document.querySelector('#detail-roles-edit .button.is-success');
    }
    
    if (!saveButton) {
        alert('Unable to find save button. Please refresh the page and try again.');
        return;
    }

    // Disable save button to prevent double-clicks
    const originalText = saveButton.innerHTML;
    saveButton.disabled = true;
    saveButton.innerHTML = '<span class="icon"><i class="fas fa-spinner fa-spin"></i></span><span>Saving...</span>';

    // Send PUT request to update user roles
    fetch(`/training/admin/users/${userId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin',
        body: JSON.stringify({ roles: roles })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Show success message briefly
            saveButton.innerHTML = '<span class="icon"><i class="fas fa-check"></i></span><span>Saved!</span>';
            
            // Determine how to refresh the content
            if (userDetailContent) {
                // In modal context - reload the modal content
                setTimeout(() => {
                    if (typeof showUserDetailModal === 'function') {
                        showUserDetailModal(userId);
                    } else {
                        // Fallback: reload the page
                        location.reload();
                    }
                }, 1000);
            } else {
                // In embedded context - reload the page
                setTimeout(() => {
                    location.reload();
                }, 1000);
            }
        } else {
            throw new Error(data.error || 'Unknown error occurred');
        }
    })
    .catch(error => {
        console.error('Error saving user roles:', error);
        alert('Failed to save user roles: ' + error.message);
        
        // Restore save button
        saveButton.disabled = false;
        saveButton.innerHTML = originalText;
    });
}

// Global state for user data and filtering
let allUsers = []; // Store all users from initial request
let usersLoaded = false; // Track if initial request is complete
let filterTimeout = null; // For debouncing client-side filtering

// Initial data loading - fetch all users once
function loadAllUsers() {
    console.log('Loading all users from new endpoint...');
    
    // Show loading state
    showLoadingState();
    
    // Fetch ALL users from the new dedicated endpoint
    fetch('/training/admin/users', {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then(response => {
            console.log('All users response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Received all users data:', data.users?.length || 0, 'users');
            allUsers = data.users || [];
            usersLoaded = true;
            
            // Apply current filters to the loaded data
            applyCurrentFilters();
        })
        .catch(error => {
            console.error('Error loading all users:', error);
            showNotification('Error loading users. Please refresh the page and try again.', 'is-danger');
        });
}

function showLoadingState() {
    console.log('Showing loading state');
    const tbody = document.getElementById('users-table-body');
    if (tbody) {
        console.log('Found users table body, setting loading content');
        tbody.innerHTML = '<tr><td colspan="8" class="has-text-centered"><i class="fas fa-spinner fa-spin"></i> Loading users...</td></tr>';
        
        // Also update the user count
        updateUserCounts(0, 0);
    } else {
        console.error('Could not find users table body element');
    }
}

// Client-side filtering with debouncing
function filterUsers() {
    console.log('filterUsers called (debounced)');
    
    // Cancel any existing timeout
    if (filterTimeout) {
        clearTimeout(filterTimeout);
        filterTimeout = null;
    }
    
    // Set up debounced filtering with 500ms delay (faster than server requests)
    filterTimeout = setTimeout(() => {
        applyCurrentFilters();
    }, 500);
}

// Immediate filtering for dropdowns
function filterUsersImmediate() {
    console.log('filterUsersImmediate called');
    
    // Cancel any existing timeout
    if (filterTimeout) {
        clearTimeout(filterTimeout);
        filterTimeout = null;
    }
    
    // Apply filters immediately
    applyCurrentFilters();
}

// Apply current search/filter values to the loaded user data
function applyCurrentFilters() {
    if (!usersLoaded) {
        console.log('Users not loaded yet, skipping filter');
        return;
    }
    
    const searchText = document.getElementById('search-text')?.value?.trim()?.toLowerCase() || '';
    const filterRole = document.getElementById('filter-role')?.value?.trim()?.toLowerCase() || 'all';
    
    console.log('Applying client-side filters:', { searchText, filterRole, totalUsers: allUsers.length });
    
    let filteredUsers = allUsers;
    
    // Apply role filter (skip if 'all' is selected)
    if (filterRole && filterRole !== 'all') {
        filteredUsers = filteredUsers.filter(user => {
            return user.roles.some(role => role.toLowerCase() === filterRole);
        });
        console.log(`After role filter (${filterRole}):`, filteredUsers.length, 'users');
    }
    
    // Apply text search filter
    if (searchText) {
        filteredUsers = filteredUsers.filter(user => {
            const username = (user.username || '').toLowerCase();
            const fullName = (user.full_name || '').toLowerCase();
            return username.includes(searchText) || fullName.includes(searchText);
        });
        console.log(`After text filter (${searchText}):`, filteredUsers.length, 'users');
    }
    
    console.log('Final filtered results:', filteredUsers.length, 'of', allUsers.length, 'users');
    
    // Update the display
    updateUserTable(filteredUsers);
    updateUserCounts(allUsers.length, filteredUsers.length);
}

function updateUserTable(users) {
    const tbody = document.getElementById('users-table-body');
    if (!tbody) {
        console.error('Could not find users table body');
        return;
    }
    
    // Clear existing content
    tbody.innerHTML = '';

    if (users && users.length > 0) {
        // Add user rows
        users.forEach(user => {
            const row = document.createElement('tr');
            row.className = 'user-row is-clickable';
            row.setAttribute('data-id', user.id);
            row.setAttribute('data-username', user.username);
            row.setAttribute('data-fullname', user.full_name);
            row.setAttribute('data-roles', user.roles.join(','));
            row.setAttribute('data-status', user.status);
            row.setAttribute('data-created', user.created_at ? user.created_at.split('T')[0] : '');
            row.setAttribute('onclick', `showUserDetailModal(${user.id})`);
            row.setAttribute('title', 'Click to view detailed user information');
            row.style.cursor = 'pointer';

            row.innerHTML = `
                <td>
                    <strong>${user.id}</strong>
                </td>
                <td>
                    <span class="tag is-primary">
                        ${user.username}
                    </span>
                </td>
                <td>
                    ${user.full_name || 'No name'}
                </td>
                <td>
                    ${user.roles.map(role => `<span class="tag is-small ${getRoleTagClass(role)}">${role}</span>`).join(' ')}
                </td>
                <td>
                    <span class="tag is-small ${getStatusTagClass(user.status)}">${user.status}</span>
                </td>
                <td>
                    <span class="tag is-small is-info">${user.discussion_count}</span>
                </td>
                <td>
                    <span class="tag is-small is-success">${user.diagram_count}</span>
                </td>
                <td>
                    <small>${user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}</small>
                </td>
            `;

            tbody.appendChild(row);
        });
    } else {
        // Show no results message
        const row = document.createElement('tr');
        row.innerHTML = `
            <td colspan="8" class="has-text-centered">
                <strong>No users found.</strong><br>
                No users match the current search criteria.
            </td>
        `;
        tbody.appendChild(row);
    }
}

function getRoleTagClass(role) {
    switch(role) {
        case 'admin': return 'is-danger';
        case 'auditor': return 'is-warning';
        case 'subscriber': return 'is-info';
        default: return 'is-light';
    }
}

function getStatusTagClass(status) {
    switch(status) {
        case 'confirmed': return 'is-success';
        case 'pending': return 'is-warning';
        default: return 'is-light';
    }
}

function updateUserCounts(total, showing) {
    console.log(`Updating user counts: showing ${showing} of ${total} total`);
    const countElement = document.querySelector('.user-count');
    if (countElement) {
        if (showing === total) {
            countElement.textContent = `Showing ${showing} users`;
        } else {
            countElement.textContent = `Showing ${showing} of ${total} users`;
        }
        console.log('Updated user count display');
    } else {
        console.error('Could not find user count element');
    }
}

function clearFilters() {
    console.log('Clearing all filters');
    document.getElementById('search-text').value = '';
    document.getElementById('filter-role').value = 'all'; // Reset to show all roles
    // Apply filters immediately after clearing
    filterUsersImmediate();
}

// Notification helper function
function showNotification(message, type = 'is-info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <button class="delete" onclick="this.parentElement.remove()"></button>
        ${message}
    `;
    
    // Insert at top of page
    const container = document.querySelector('.container') || document.body;
    container.insertBefore(notification, container.firstChild);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Initialize event listeners when DOM is loaded
function initializeUserDetailComponent() {
    console.log('Initializing user detail component - DOM loaded');
    
    // Check if we're on the admin page first
    const usersContainer = document.getElementById('users-section-container');
    console.log('Users container found:', !!usersContainer);
    
    if (usersContainer) {
        console.log('Admin page detected - setting up user management');
        
        // Add event listeners for search functionality
        const searchInput = document.getElementById('search-text');
        const roleSelect = document.getElementById('filter-role');
        
        console.log('Search input found:', !!searchInput);
        console.log('Role select found:', !!roleSelect);
        
        if (searchInput) {
            searchInput.addEventListener('input', function() {
                // Use debounced filtering for text input (client-side only)
                filterUsers();
            });
        }
        
        if (roleSelect) {
            roleSelect.addEventListener('change', function() {
                // Use immediate filtering for role changes (client-side only)
                filterUsersImmediate();
            });
        }
        
        // Load all users immediately - this is the ONLY API request
        loadAllUsers();
    } else {
        console.log('Not on admin page, skipping user management setup');
    }
}

// Auto-initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeUserDetailComponent);

// Create new diagram function - always gets user ID from user detail component data
function createNewDiagram() {
    const name = prompt('Enter a name for the new diagram:');
    if (!name || !name.trim()) {
        return;
    }
    
    // Always look for the user detail component data attribute
    const userInfoBox = document.querySelector('[data-user-id]');
    if (!userInfoBox) {
        alert('Unable to determine target user. Please refresh the page and try again.');
        return;
    }
    
    const targetUserId = userInfoBox.getAttribute('data-user-id');
    console.log('Creating diagram for user ID:', targetUserId);
    
    const requestBody = {
        name: name.trim(),
        user_id: parseInt(targetUserId)
    };
    
    fetch('/training/diagrams', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin',
        body: JSON.stringify(requestBody)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Check if we're in a modal context to determine refresh strategy
            const isInModal = document.getElementById('userDetailModal')?.classList.contains('is-active');
            if (isInModal) {
                // Refresh the user detail modal to show the new diagram
                showUserDetailModal(targetUserId);
            } else {
                // Reload the page to show the new diagram
                location.reload();
            }
        } else {
            alert('Error creating diagram: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error creating diagram:', error);
        alert('Error creating diagram: ' + error.message);
    });
}

// Clear user database function
function clearUserDiagramData(userId, username) {
    const message = `Are you sure you want to clear the database for user "${username}"?
    
This will permanently:
- Reset their database JSON column to empty ({})
- Remove all their stored PDP data
- Remove all their personal data points

This action cannot be undone!`;

    if (confirm(message)) {
        fetch(`/training/admin/users/${userId}/clear-database?confirm=true`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('User database cleared successfully!');
                // Refresh the user detail modal or reload page
                const userInfoBox = document.querySelector('[data-user-id]');
                if (userInfoBox) {
                    const currentUserId = userInfoBox.getAttribute('data-user-id');
                    if (currentUserId == userId) {
                        showUserDetailModal(userId);
                    } else {
                        location.reload();
                    }
                } else {
                    location.reload();
                }
            } else {
                alert('Server returned message: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error clearing user database:', error);
            alert('Server returned error clearing user database: ' + error);
        });
    }
}

// Hide user data modal function
function hideUserData() {
    const modal = document.getElementById('userDataModal');
    if (modal) {
        modal.classList.remove('is-active');
    }
}

// Delete diagram function
function deleteDiagram(diagramId, diagramName) {
    const message = `Are you sure you want to delete diagram "${diagramName}"?

This will permanently delete:
- The diagram and all its data
- All associated discussions
- All extracted data

This action cannot be undone!`;

    if (confirm(message)) {
        fetch(`/training/diagrams/${diagramId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Check if we're in a modal context to determine refresh strategy
                const isInModal = document.getElementById('userDetailModal')?.classList.contains('is-active');
                if (isInModal) {
                    // Refresh the user detail modal to show updated diagrams
                    const userInfoBox = document.querySelector('[data-user-id]');
                    if (userInfoBox) {
                        const userId = userInfoBox.getAttribute('data-user-id');
                        showUserDetailModal(userId);
                    } else {
                        location.reload();
                    }
                } else {
                    // Reload the page to show updated diagrams
                    location.reload();
                }
            } else {
                alert('Error deleting diagram: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error deleting diagram:', error);
            alert('Error deleting diagram: ' + error.message);
        });
    }
}

// Make functions globally available for onclick handlers
window.showUserDetailModal = showUserDetailModal;
window.hideUserDetailModal = hideUserDetailModal;
window.startEditRoles = startEditRoles;
window.cancelEditRoles = cancelEditRoles;
window.saveUserRoles = saveUserRoles;
window.filterUsers = filterUsers;
window.clearFilters = clearFilters;
window.createNewDiagram = createNewDiagram;
window.hideUserData = hideUserData;
window.deleteDiagram = deleteDiagram;