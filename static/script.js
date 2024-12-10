async function addStock() {
    const stockName = document.getElementById('stockName').value;
    const response = await fetch('/add-stock', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `stock_name=${encodeURIComponent(stockName)}`
    });
    
    const data = await response.json();
    if (data.success) {
        location.reload();
    } else {
        alert(data.error);
    }
}

async function removeStock(code) {
    const response = await fetch(`/remove-stock/${code}`, {
        method: 'POST'
    });
    
    const data = await response.json();
    if (data.success) {
        document.getElementById(`stock-${code}`).remove();
    } else {
        alert(data.error);
    }
} 