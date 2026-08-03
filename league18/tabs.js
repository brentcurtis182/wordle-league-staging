// Tab functionality for Wordle League pages
document.addEventListener('DOMContentLoaded', function() {
    // Get all tab buttons
    const tabButtons = document.querySelectorAll('.tab-button');
    
    // Add click event listener to each button
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Get the data-tab attribute value (tab id to show)
            const tabToShow = this.getAttribute('data-tab');
            
            // Remove active class from all tab buttons and content
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Add active class to clicked button and corresponding content
            this.classList.add('active');
            document.getElementById(tabToShow).classList.add('active');
        });
    });
});
