document.addEventListener("DOMContentLoaded", function() {
    const dropdown = document.getElementById('dropdown');
    const resultsTable = document.getElementById('results-table').getElementsByTagName('tbody')[0];
    const addButton = document.getElementById('add');
    const textarea = document.getElementById('results');
    const clearButton = document.getElementById('clear');
    const exportButton = document.getElementById('export');
    const updateButton = document.getElementById('update');
    const number_of_days = document.getElementById('days');
    const searchBar = document.getElementById('search-bar');
    const searchButton = document.getElementById('search-button');

    let lastSearch = "";

    // Modal elements
    const modal = document.getElementById('progress-modal');
    const closeModal = document.getElementsByClassName('close')[0];
    const modalMessage = document.getElementById('modal-message');
    const modalSpinner = document.getElementById('modal-spinner');
    const modalAcceptButton = document.getElementById('modal-accept');

    // Export modal elements
    const exportModal = document.getElementById('export-modal');
    const closeExportModal = document.getElementsByClassName('close-export')[0];
    const exportSimpleButton = document.getElementById('export-simple');
    const exportWhoisButton = document.getElementById('export-whois');
    const exportExtendedWhoisButton = document.getElementById('export-extended-whois');

    // Function to show the modal
    function showModal() {
        modal.style.display = 'block';
        modalMessage.innerHTML = 'Updating database, please wait...';
        modalSpinner.style.display = 'block';
        modalAcceptButton.style.display = 'none';
    }

    // Function to hide the modal
    function hideModal() {
        modal.style.display = 'none';
    }

    closeModal.onclick = function() {
        hideModal();
    }

    modalAcceptButton.onclick = function() {
        hideModal();
    }

    window.onclick = function(event) {
        if (event.target == modal) {
            hideModal();
        }
    }

    // Function to show the export modal
    function showExportModal() {
        exportModal.style.display = 'block';
    }

    // Function to hide the export modal
    function hideExportModal() {
        exportModal.style.display = 'none';
    }

    closeExportModal.onclick = function() {
        hideExportModal();
    }

    window.onclick = function(event) {
        if (event.target == exportModal) {
            hideExportModal();
        }
    }

    dropdown.addEventListener('change', function() {
        const selectedPattern = dropdown.value;
        fetch(`/get_domains?pattern=${selectedPattern}`)
            .then(response => response.json())
            .then(data => updateTable(data.domains))
            .catch(error => console.error('Error fetching domains:', error));
    });

    searchButton.addEventListener('click', function() {
        const query = searchBar.value.trim();
        if (query === "") {
            alert("[!]Error, empty field");
        } else {
            lastSearch = query;
            fetch(`/search_domains?query=${query}`)
                .then(response => response.json())
                .then(data => {
                    updateTable(data.domains);
                    dropdown.selectedIndex = 0; // Reset the dropdown to the first option
                })
                .catch(error => console.error('Error fetching domains:', error));
        }
    });

    updateButton.addEventListener('click', function() {
        const days = number_of_days.value.trim();
        showModal(); // Show the modal when the update starts
        fetch('/run-script', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ days: days })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Success:', data);
            let message = data.dates.map(date => `The database of day ${date} was updated correctly.`).join('<br>');
            if (data.not_available_dates && data.not_available_dates.length > 0) {
                message += '<br>' + data.not_available_dates.map(date => `The database of day ${date} is not available yet.`).join('<br>');
            }
            message += `<br><br><span class="domain-count">[${data.line_count} domains]</span>`;
            modalMessage.innerHTML = message;
            modalSpinner.style.display = 'none';
            modalAcceptButton.style.display = 'inline-block';
        })
        .catch((error) => {
            console.error('Error:', error);
            modalMessage.textContent = 'It wasn\'t possible to update the database.';
            modalSpinner.style.display = 'none';
            modalAcceptButton.style.display = 'inline-block';
        });
    });

    exportButton.addEventListener('click', function() {
        showExportModal();
    });

    exportSimpleButton.addEventListener('click', function() {
        generateTxtFile();
        hideExportModal();
    });

    exportWhoisButton.addEventListener('click', function() {
        generateWhoisTxtFile(false);
        hideExportModal();
    });

    exportExtendedWhoisButton.addEventListener('click', function() {
        generateWhoisTxtFile(true);
        hideExportModal();
    });

    addButton.addEventListener('click', function() {
        const selectedDomains = getSelectedDomains();
        const selectedPattern = dropdown.selectedIndex === 0 ? lastSearch : dropdown.options[dropdown.selectedIndex].text;
        addDomainsToTextarea(selectedDomains, selectedPattern);
    });

    clearButton.addEventListener('click', function() {
        textarea.value = "";
    });

    function updateTable(domains) {
        while (resultsTable.firstChild) {
            resultsTable.removeChild(resultsTable.firstChild);
        }

        domains.forEach(domain => {
            const row = document.createElement('tr');

            const checkboxCell = document.createElement('td');
            checkboxCell.classList.add('checkbox');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = domain;
            checkboxCell.appendChild(checkbox);
            row.appendChild(checkboxCell);

            const domainCell = document.createElement('td');
            domainCell.textContent = domain;
            row.appendChild(domainCell);

            resultsTable.appendChild(row);
        });
    }

    function getSelectedDomains() {
        const checkboxes = resultsTable.querySelectorAll('input[type="checkbox"]:checked');
        const selectedDomains = [];
        checkboxes.forEach(checkbox => {
            selectedDomains.push(checkbox.value);
        });
        return selectedDomains;
    }

    function addDomainsToTextarea(domains, pattern) {
        textarea.value += `[+]____${pattern}____[+]\n`;
        domains.forEach(domain => {
            textarea.value += domain + '\n';
        });
        textarea.value += '\n\n'; // Añadir dos saltos de línea entre cada grupo
    }

    function generateTxtFile() {
        const blob = new Blob([textarea.value], { type: 'text/plain' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'fake-domains.txt';
        link.click();
        URL.revokeObjectURL(link.href);
    }

    function generateWhoisTxtFile(extended) {
        const domains = textarea.value.split('\n').filter(line => line.trim() !== "" && !line.startsWith("[+]____"));
        fetch('/whois_export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ domains: domains, extended: extended })
        })
        .then(response => response.json())
        .then(data => {
            if (extended) {
                if (data.whoisFile) {
                    downloadFile(data.whoisFile, 'fake-domains-extended-whois.txt');
                } else {
                    console.error('Error in response data:', data);
                }
            } else {
                if (data.reliabilityFile) {
                    downloadFile(data.reliabilityFile, 'fake-domains-reliability.txt');
                } else {
                    console.error('Error in response data:', data);
                }
            }
        })
        .catch(error => console.error('Error generating WHOIS TXT file:', error));
    }

    function downloadFile(filePath, fileName) {
        const link = document.createElement('a');
        link.href = `/download?file=${encodeURIComponent(filePath)}`;
        link.download = fileName;
        link.click();
    }
});
