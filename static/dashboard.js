document.addEventListener('DOMContentLoaded', () => {
    
    const totalCountEl = document.getElementById('total-count');
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

    const historyBody = document.getElementById('history-body');
    if (historyBody) {
        historyBody.innerHTML = ''; 
        
        historyData.forEach(item => {
            if (item.sentiment === 'Positive') positiveCount++;
            else if (item.sentiment === 'Negative' || item.sentiment === 'Toxic') negativeCount++;
            else neutralCount++;

            const tr = document.createElement('tr');
            
            const rawDate = item.created_at || item.date;
            const dateObj = rawDate ? new Date(rawDate) : new Date();

            const tdDate = document.createElement('td');
            tdDate.textContent = formatDate(dateObj);
            
            const tdText = document.createElement('td');
            tdText.textContent = item.text || '';
            
            const sentimentStr = item.sentiment || 'Neutral';
            let emoji = '😐';
            let badgeClass = sentimentStr.toLowerCase();
            
            if (sentimentStr === 'Positive') emoji = '😊';
            else if (sentimentStr === 'Negative' || sentimentStr === 'Toxic') {
                emoji = '😠';
                badgeClass = 'negative';
            }

            const tdSentiment = document.createElement('td');
            const badge = document.createElement('span');
            badge.className = `badge ${badgeClass}`;
            badge.innerHTML = `<span>${emoji}</span> ${badgeClass === 'negative' ? 'Negative' : sentimentStr}`;
            tdSentiment.appendChild(badge);

            const tdAction = document.createElement('td');
            if (item._id) {
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = `/delete/${item._id}`;
                form.style.display = 'inline';
                const btn = document.createElement('button');
                btn.type = 'submit';
                btn.textContent = 'Delete';
                btn.className = 'btn-delete';
                form.appendChild(btn);
                tdAction.appendChild(form);
            }

            tr.appendChild(tdDate);
            tr.appendChild(tdText);
            tr.appendChild(tdSentiment);
            tr.appendChild(tdAction);

            historyBody.appendChild(tr);
        });

        animateValue(totalCountEl, 0, historyData.length, 1000);
        animateValue(positiveCountEl, 0, positiveCount, 1000);
        animateValue(negativeCountEl, 0, negativeCount, 1000);
        animateValue(neutralCountEl, 0, neutralCount, 1000);

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
});
