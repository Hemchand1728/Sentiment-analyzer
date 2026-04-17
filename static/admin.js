document.addEventListener('DOMContentLoaded', () => {
    let globalData = [];

    // Fetch initial stats
    fetchStats();

    // Setup filter event
    document.getElementById('sentiment-filter').addEventListener('change', (e) => {
        renderTable(globalData, e.target.value);
    });
});

async function fetchStats() {
    try {
        const response = await fetch('/api/admin/stats', {
            method: 'GET',
            credentials: 'same-origin'
        });
        const data = await response.json();
        console.log('admin stats', data);
        
        if (data.error) {
            alert('Error loading admin stats: ' + data.error);
            return;
        }

        globalData = data.table_data;

        // Render everything
        renderPieChart(data.pie_chart);
        renderBarChart(data.bar_chart);
        renderLineChart(data.trends);
        renderLeaderboard(data.top_negative);
        renderTable(globalData, 'All');
        
        // Alert if recent negative content detected
        checkRecentNegative(data.table_data);

    } catch (e) {
        console.error('Failed to load stats', e);
    }
}

function checkRecentNegative(history) {
    // Show alert if top item is negative and within last 24h
    if (!history || history.length === 0) return;
    const topItem = history[0];
    if (topItem.sentiment === 'Negative') {
        const zone = document.getElementById('alert-zone');
        zone.innerHTML = `<span style="background: #ef4444; color: white; padding: 0.5rem 1rem; border-radius: 999px; font-weight: 600; font-size: 0.875rem; box-shadow: 0 4px 6px -1px rgba(239, 68, 68, 0.4); animation: pulse 2s infinite;">⚠️ New Negative Activity Detected!</span>`;
    }
}

// =====================
// CHART RENDERING
// =====================

function renderPieChart(pieData) {
    const ctx = document.getElementById('pieChart').getContext('2d');
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Positive', 'Negative', 'Neutral'],
            datasets: [{
                data: [
                    pieData.Positive || 0,
                    pieData.Negative || 0,
                    pieData.Neutral || 0
                ],
                backgroundColor: ['#22c55e', '#f97316', '#64748b'],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: { position: 'right' }
            },
            animation: {
                animateScale: true,
                animateRotate: true,
                duration: 1500,
                easing: 'easeOutQuart'
            }
        }
    });
}

function renderBarChart(barData) {
    const ctx = document.getElementById('barChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: barData.labels,
            datasets: [{
                label: 'Comments',
                data: barData.data,
                backgroundColor: '#3b82f6',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            },
            animation: {
                duration: 1200,
                easing: 'easeOutBounce'
            }
        }
    });
}

function renderLineChart(lineData) {
    const ctx = document.getElementById('lineChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: lineData.labels,
            datasets: [
                {
                    label: 'Positive',
                    data: lineData.positive,
                    borderColor: '#22c55e',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Negative',
                    data: lineData.negative,
                    borderColor: '#f97316',
                    backgroundColor: 'rgba(249, 115, 22, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Neutral',
                    data: lineData.neutral,
                    borderColor: '#64748b',
                    backgroundColor: 'rgba(100, 116, 139, 0.12)',
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: { position: 'top' }
            },
            scales: {
                y: { beginAtZero: true }
            },
            animation: {
                duration: 2000,
                easing: 'easeInOutQuart'
            }
        }
    });
}

function renderLeaderboard(topNegative) {
    const list = document.getElementById('leaderboard');
    if (!topNegative || topNegative.length === 0) {
        list.innerHTML = `<li class="leaderboard-item" style="color: #64748b; justify-content: center;">No negative users found.</li>`;
        return;
    }
    
    list.innerHTML = topNegative.map((u, i) => `
        <li class="leaderboard-item">
            <span style="font-weight: 500;">
                <span style="display:inline-block; width:24px; color:#ef4444">${i === 0 ? '🏆' : `#${i+1}`}</span>
                ${u.user}
            </span>
            <span style="background: #fef2f2; color: #dc2626; padding: 0.2rem 0.6rem; border-radius: 99px; font-size: 0.875rem; font-weight: 600;">
                ${u.count} negative posts
            </span>
        </li>
    `).join('');
}


// =====================
// MODERATION TABLE & ACTIONS
// =====================

function renderTable(history, filter) {
    const tbody = document.getElementById('mod-tbody');
    
    let filtered = history;
    if (filter !== 'All') {
        filtered = history.filter(h => h.sentiment === filter);
    }

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: #64748b;">No items found.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(item => {
        const isFlagged = item.flagged;
        
        let sentimentStr = item.sentiment;
        if (sentimentStr === 'Positive') sentimentStr = '😊 Positive';
        else if (sentimentStr === 'Negative') sentimentStr = '😠 Negative';
        else sentimentStr = '😐 Neutral';

        return `
            <tr class="${isFlagged ? 'row-toxic' : ''}">
                <td style="font-size: 0.875rem; color: #64748b;">${item.created_at}</td>
                <td style="font-weight: 500;">${item.user}</td>
                <td style="max-width: 300px; word-wrap: break-word;">
                    ${isFlagged ? '<span class="flagged-icon">🚩</span>' : ''}
                    ${item.text}
                </td>
                <td><span style="background: ${getBadgeColor(item.sentiment)}; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold;">${sentimentStr}</span></td>
                <td style="white-space: nowrap;">
                    ${!isFlagged ? 
                        `<button class="mod-btn btn-flag" onclick="modAction('flag', '${item._id}')">Flag</button>` : 
                        `<button class="mod-btn btn-safe" onclick="modAction('safe', '${item._id}')">Mark Safe</button>`
                    }
                    <button class="mod-btn btn-del" onclick="modAction('delete', '${item._id}')">Del</button>
                    <button class="mod-btn btn-block" onclick="blockUser('${item.user}')">Block User</button>
                </td>
            </tr>
        `;
    }).join('');
}

function getBadgeColor(sentiment) {
    if (sentiment === 'Positive') return '#22c55e';
    if (sentiment === 'Negative') return '#f97316';
    return '#64748b';
}

async function modAction(action, id) {
    if (action === 'delete' && !confirm('Are you sure you want to delete this comment?')) return;
    
    try {
        const res = await fetch(`/admin/action/${action}/${id}`, {
            method: 'POST',
            credentials: 'same-origin'
        });
        const data = await res.json();
        if (data.success) {
            // refresh data
            fetchStats();
        } else {
            alert('Action failed: ' + data.error);
        }
    } catch (e) {
        alert('Server error');
    }
}

async function blockUser(email) {
    if (!confirm(`Are you sure you want to permanently block user ${email}?`)) return;

    try {
        const res = await fetch(`/admin/block`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email })
        });
        const data = await res.json();
        if (data.success) {
            alert(data.message);
        } else {
            alert('Failed to block: ' + data.error);
        }
    } catch (e) {
        alert('Server error');
    }
}
