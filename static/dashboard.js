document.addEventListener('DOMContentLoaded', () => {
    
    const positiveCountEl = document.getElementById('positive-count');
    const negativeCountEl = document.getElementById('negative-count');
    const neutralCountEl = document.getElementById('neutral-count');

    const historyData = window.historyData || [];

    let positiveCount = 0;
    let negativeCount = 0;
    let neutralCount = 0;

    const formatDate = (date) => {
        return new Intl.DateTimeFormat('en-US', {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        }).format(date);
    };

    const keywordsGrid = document.getElementById('keywords-grid');
    if (keywordsGrid) {
        keywordsGrid.innerHTML = ''; 
        
        historyData.forEach(item => {
            positiveCount += (item.positive || 0);
            negativeCount += (item.negative || 0);
            neutralCount += (item.neutral || 0);

            const card = document.createElement('div');
            card.className = 'saas-card keyword-card';
            
            const rawDate = item.latest_date;
            const dateObj = rawDate ? new Date(rawDate) : new Date();

            let keywordLabel = item.keyword || 'Unknown';
            // Title case the keyword
            keywordLabel = keywordLabel.charAt(0).toUpperCase() + keywordLabel.slice(1);

            card.innerHTML = `
                <div class="keyword-header" style="justify-content: space-between;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <h3 class="keyword-title" style="margin: 0;">#${keywordLabel}</h3>
                        <span class="keyword-date" style="margin: 0;">${formatDate(dateObj)}</span>
                    </div>
                    <form action="/delete-keyword/${encodeURIComponent(item.keyword)}" method="POST" style="margin: 0;" onsubmit="return confirm('Are you sure you want to delete all history for this keyword?');">
                        <button type="submit" style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); color: #ef4444; border-radius: 4px; padding: 4px 10px; cursor: pointer; transition: all 0.2s; font-size: 0.85rem;" onmouseover="this.style.background='rgba(239, 68, 68, 0.3)'" onmouseout="this.style.background='rgba(239, 68, 68, 0.15)'">
                            Delete
                        </button>
                    </form>
                </div>
                <div class="keyword-stats">
                    <div class="k-stat k-positive">
                        <span class="k-icon">😊</span>
                        <span class="k-value">${item.positive || 0}</span>
                    </div>
                    <div class="k-stat k-negative">
                        <span class="k-icon">😠</span>
                        <span class="k-value">${item.negative || 0}</span>
                    </div>
                    <div class="k-stat k-neutral">
                        <span class="k-icon">😐</span>
                        <span class="k-value">${item.neutral || 0}</span>
                    </div>
                </div>
                <div class="keyword-total">
                    Total Tweets: <strong>${item.total || 0}</strong>
                </div>
            `;

            keywordsGrid.appendChild(card);
        });

        if (positiveCountEl) animateValue(positiveCountEl, 0, positiveCount, 1000);
        if (negativeCountEl) animateValue(negativeCountEl, 0, negativeCount, 1000);
        if (neutralCountEl) animateValue(neutralCountEl, 0, neutralCount, 1000);

        const ctx = document.getElementById('sentimentChart');
        if (ctx && historyData.length > 0) {
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Positive', 'Negative', 'Neutral'],
                    datasets: [{
                        data: [positiveCount, negativeCount, neutralCount],
                        backgroundColor: [
                            '#22c55e', // vibrant green for positive
                            '#f97316', // orange for negative
                            '#64748b'  // muted slate for neutral
                        ],
                        hoverOffset: 4,
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 20,
                                font: {
                                    family: "'Inter', 'Segoe UI', sans-serif",
                                    size: 14,
                                    weight: 500
                                }
                            }
                        }
                    },
                    cutout: '65%',
                    animation: {
                        animateScale: true,
                        animateRotate: true,
                        duration: 1500,
                        easing: 'easeOutQuart'
                    }
                }
            });
        } else if (ctx) {
            // Hide the chart section if no data
            ctx.parentElement.style.display = 'none';
        }
    }
    
    function animateValue(obj, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            obj.innerHTML = Math.floor(progress * (end - start) + start);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }
    
    // Load User Feedback
    fetch('/api/user/feedback')
        .then(res => res.json())
        .then(data => {
            const feedbackList = document.getElementById('my-feedback-list');
            const notificationBanner = document.getElementById('notification-banner');
            let hasUnseenResolved = false;

            if (data.error) {
                feedbackList.innerHTML = `<div style="color: red;">Error loading feedback</div>`;
                return;
            }

            if (data.length === 0) {
                feedbackList.innerHTML = `<div style="color: #6b7280; font-size: 0.9rem;">No feedback submitted yet.</div>`;
                return;
            }

            let html = `<div style="display: flex; flex-direction: column; gap: 10px;">`;
            data.forEach(item => {
                if (item.status === 'resolved' && !item.seen) {
                    hasUnseenResolved = true;
                }

                const statusColor = item.status === 'resolved' ? '#166534' : '#b45309';
                const statusBg = item.status === 'resolved' ? '#dcfce7' : '#fef3c7';

                html += `
                    <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; background: #fff;">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                            <span style="font-weight: 600; font-size: 0.85rem; color: #4b5563;">${item.type}</span>
                            <span style="background: ${statusBg}; color: ${statusColor}; padding: 2px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">
                                ${item.status}
                            </span>
                        </div>
                        <div style="font-size: 0.95rem; color: #111827; margin-bottom: 8px;">${item.message}</div>
                        <div style="font-size: 0.75rem; color: #9ca3af;">${item.created_at || ''}</div>
                    </div>
                `;
            });
            html += `</div>`;
            if (feedbackList) feedbackList.innerHTML = html;

            if (hasUnseenResolved && notificationBanner) {
                // Mark as seen and show notification ONLY if backend confirmed update
                fetch('/api/user/feedback/mark-seen', { method: 'POST' })
                    .then(r => r.json())
                    .then(d => {
                        if (d.success === true) {
                            notificationBanner.style.display = 'block';
                            setTimeout(() => {
                                notificationBanner.style.opacity = "0";
                                setTimeout(() => {
                                    if (notificationBanner) notificationBanner.remove();
                                }, 500);
                            }, 5000);
                        }
                    })
                    .catch(e => console.error("Error marking feedback seen:", e));
            }
        })
        .catch(err => {
            const feedbackList = document.getElementById('my-feedback-list');
            if (feedbackList) feedbackList.innerHTML = `<div style="color: red;">Failed to load feedback</div>`;
        });
});
