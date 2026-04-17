// Helper to display messages
function showMessage(type, msg) {
  const alertEl = document.getElementById('alertMsg');
  if (alertEl) {
    alertEl.className = `alert ${type}`;
    alertEl.innerText = msg;
  }
}

// Global Auth Check for Protected Pages
function checkAuth(requiredRole = null) {
  const token = localStorage.getItem('token');
  const role = localStorage.getItem('role');

  if (!token) {
    window.location.href = '/login.html';
    return null;
  }

  if (requiredRole && role !== requiredRole) {
    window.location.href = '/dashboard.html';
    return null;
  }

  return token;
}

// Login & Registration handlers
async function handleAuth(url, body) {
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    
    const data = await res.json();
    
    if (!res.ok) {
      showMessage('error', data.error || 'Authentication error');
      return false;
    }

    if (data.token) {
      localStorage.setItem('token', data.token);
      localStorage.setItem('role', data.role);
    }
    return data;
  } catch (error) {
    showMessage('error', 'Network error. Try again.');
    return false;
  }
}

function handleLogout() {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  window.location.href = '/login.html';
}
