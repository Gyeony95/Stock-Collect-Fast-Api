async function addStock() {
    const stockName = document.getElementById('stockName').value;
    if (!stockName.trim()) return;  // 빈 입력 방지

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
    if (!confirm('정말 이 종목을 삭제하시겠습니까?')) return;

    try {
        const response = await fetch(`/remove-stock/${code}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        if (data.success) {
            document.getElementById(`stock-${code}`).remove();
        } else {
            alert(data.error || '종목 제거 중 오류가 발생했습니다.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('종목 제거 중 오류가 발생했습니다.');
    }
}

// 폼 제출 처리
function handleSubmit(event) {
    event.preventDefault();
    addStock();
} 