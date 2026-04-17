async function analyze() {
    const textElement = document.getElementById('text');
    const resultElement = document.getElementById('result');
    const text = textElement.value.trim();

    if (!text) {
        resultElement.innerText = "Please enter some text.";
        resultElement.className = "neutral";
        return;
    }

    resultElement.innerText = "Analyzing...";
    resultElement.className = "neutral";

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: text })
        });

        const data = await response.json();

        if (data.error) {
            resultElement.innerText = data.error;
            resultElement.className = "alert negative";
            resultElement.style.display = 'block';
            return;
        }

        const sentiment = data.sentiment;

        if (sentiment === "Positive") {
            resultElement.innerHTML = "<span class='badge positive'><span>😊</span> Positive</span>";
        } else if (sentiment === "Negative" || sentiment === "Toxic") {
            resultElement.innerHTML = "<span class='badge negative'><span>😠</span> Negative</span>";
        } else {
            resultElement.innerHTML = "<span class='badge neutral'><span>😐</span> Neutral</span>";
        }
        resultElement.style.display = 'block';

    } catch (error) {
        resultElement.innerText = "Server error. Try again.";
        resultElement.className = "alert negative";
        resultElement.style.display = 'block';
    }
}
