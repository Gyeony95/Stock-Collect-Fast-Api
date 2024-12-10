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
    try {
        const response = await fetch(`/remove-stock/${code}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        if (data.success) {
            const element = document.getElementById(`stock-${code}`);
            if (element) {
                element.remove();
            }
        } else {
            alert(data.error || '종목 제거 중 오류가 발생했습니다.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('종목 제거 중 오류가 발생했습니다.');
    }
} 