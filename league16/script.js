
document.addEventListener('DOMContentLoaded', function() {
    // Tab functionality
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to current button and content
            button.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
    
    // Style failed attempts cells based on their values
    const failedCells = document.querySelectorAll('.failed-attempts');
    failedCells.forEach(cell => {
        if (cell.textContent === '0') {
            cell.style.backgroundColor = 'transparent';
            cell.style.color = '#d7dadc';
            cell.style.fontWeight = 'normal';
        }
    });
});
        