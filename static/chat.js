// WhatsApp Chat Viewer JavaScript
document.addEventListener('DOMContentLoaded', () => {
    loadPage(config.currentPage);
    setupEventListeners();
});

let loadedPages = new Set();
let isLoading = false;
let totalLoadedMessages = 0;

function setupEventListeners() {
    // Search box input handling with debounce
    let searchTimeout;
    document.getElementById('search-box').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            loadPage(0, e.target.value);
        }, 300);
    });

    // Name selection for message alignment
    document.getElementById('my-name').addEventListener('change', applyMessageAlignment);

    // Jump box for quick navigation
    document.getElementById('jump-box').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleJump();
        }
    });

    // Batch size changes
    document.getElementById('batch-size').addEventListener('change', function() {
        config.batchSize = parseInt(this.value, 10) || config.batchSize;
        loadPage(0, document.getElementById('search-box').value);
    });

    // Infinite scroll handling
    document.getElementById('chat-container').addEventListener('scroll', function(e) {
        if (isLoading) return;
        const container = e.target;
        
        // Load next batch if near bottom
        if (container.scrollHeight - container.scrollTop - container.clientHeight < 80) {
            let nextPage = Math.max(...Array.from(loadedPages)) + 1;
            if (!loadedPages.has(nextPage)) {
                loadPage(nextPage, document.getElementById('search-box').value, null, 'append');
            }
        }
        
        // Load previous batch if near top
        if (container.scrollTop < 80) {
            let prevPage = Math.min(...Array.from(loadedPages)) - 1;
            if (prevPage >= 0 && !loadedPages.has(prevPage)) {
                loadPage(prevPage, document.getElementById('search-box').value, null, 'prepend');
            }
        }
    });
}

function loadPage(page, query = '', scrollToIndex = null, mode = 'replace') {
    if (isLoading || loadedPages.has(page)) {
        return;
    }
    isLoading = true;
    
    const url = `/api/messages?page=${page}&query=${encodeURIComponent(query)}&file=${config.encodedFile}&batch_size=${config.batchSize}`;
    
    fetch(url)
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('chat-container');
            if (data.error) {
                if (mode === 'replace') {
                    container.innerHTML = `<div class="system">Error: ${data.error}</div>`;
                }
                isLoading = false;
                return;
            }
            
            if (mode === 'replace') {
                container.innerHTML = data.html;
                loadedPages = new Set([page]);
                totalLoadedMessages = data.total_matches;
            } else if (mode === 'append') {
                container.insertAdjacentHTML('beforeend', data.html);
                loadedPages.add(page);
                totalLoadedMessages += config.batchSize;
            } else if (mode === 'prepend') {
                container.insertAdjacentHTML('afterbegin', data.html);
                loadedPages.add(page);
                totalLoadedMessages += config.batchSize;
            }
            
            renderPagination(page, data.total_matches);
            populateSenderDropdown(data.senders || []);
            applyMessageAlignment();
            isLoading = false;
            
            if (scrollToIndex !== null && scrollToIndex !== undefined) {
                setTimeout(() => {
                    const el = document.getElementById('msg-' + scrollToIndex);
                    if (el) {
                        try {
                            el.scrollIntoView({behavior: 'smooth', block: 'center'});
                        } catch (e) {
                            el.scrollIntoView();
                        }
                        el.classList.add('flash');
                        setTimeout(() => el.classList.remove('flash'), 1800);
                    }
                }, 60);
            }
        })
        .catch(err => {
            if (mode === 'replace') {
                document.getElementById('chat-container').innerHTML = '<div class="system">Failed to load messages.</div>';
            }
            isLoading = false;
        });
}

function renderPagination(page, totalMatches) {
    const totalPages = Math.ceil(totalMatches / config.batchSize);
    let html = '';
    
    if (page > 0) {
        html += `<button onclick="loadPage(${page - 1}, document.getElementById('search-box').value)">← Prev</button>`;
    }
    
    html += `Page ${page + 1} of ${totalPages || 1} (${totalMatches} matches)`;
    
    if (page < totalPages - 1) {
        html += `<button onclick="loadPage(${page + 1}, document.getElementById('search-box').value)">Next →</button>`;
    }
    
    document.getElementById('pagination').innerHTML = html;
}

function populateSenderDropdown(senders) {
    const select = document.getElementById('my-name');
    if (select.options.length <= 1) {
        senders.forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            if (name === myName) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });
    }
}

function applyMessageAlignment() {
    const myName = document.getElementById('my-name').value;
    localStorage.setItem('whatsapp_my_name_' + config.encodedFile, myName);

    document.querySelectorAll('.message').forEach(msgDiv => {
        const senderElem = msgDiv.querySelector('.sender');
        const senderName = senderElem ? senderElem.textContent : null;
        msgDiv.classList.remove('sent', 'received');
        if (myName && senderName === myName) {
            msgDiv.classList.add('sent');
        } else {
            msgDiv.classList.add('received');
        }
    });
}

function handleJump() {
    const val = document.getElementById('jump-box').value.trim();
    if (!val) return;
    
    // If numeric, treat as message number (1-based)
    if (/^\d+$/.test(val)) {
        const idx = parseInt(val, 10) - 1;
        if (isNaN(idx) || idx < 0) return;
        goToMessage(idx);
        return;
    }

    // Otherwise try to find first message matching the text
    const q = val;
    fetch(`/api/find?file=${config.encodedFile}&q=${encodeURIComponent(q)}`)
        .then(r => r.json())
        .then(data => {
            if (data && typeof data.index === 'number' && data.index >= 0) {
                goToMessage(data.index);
            } else {
                alert('No matching message found');
            }
        })
        .catch(() => alert('Failed to search'));
}

function goToMessage(globalIndex) {
    if (typeof globalIndex === 'undefined' || globalIndex === null) return;
    const pageToLoad = Math.floor(globalIndex / config.batchSize);
    const queryVal = document.getElementById('search-box').value || '';
    loadPage(pageToLoad, queryVal, globalIndex);
}