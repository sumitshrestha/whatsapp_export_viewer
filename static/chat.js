// WhatsApp Chat Viewer JavaScript
// Initialize global state on the window object
window.loadedPages = new Set();
window.isLoading = false;
window.totalLoadedMessages = 0;
window.hasMoreMessages = true;
// Initialize myName from localStorage (per-file)
try {
    if (window.config && window.config.encodedFile) {
        window.myName = localStorage.getItem('whatsapp_my_name_' + window.config.encodedFile) || '';
    } else {
        window.myName = '';
    }
} catch (e) {
    window.myName = '';
}


    // Scrolling configuration: pixel and ratio thresholds and debounce
    // Increased thresholds so we begin loading earlier on very long chats
    window.scrollLoadThresholdPx = 2000; // load when within this many pixels of bottom
    window.scrollLoadThresholdRatio = 0.18; // or within this fraction of total height
    window.scrollLoadDebounceMs = 120; // debounce scroll handler to avoid flurry of calls
    window._scrollDebounceTimer = null;
// DOM Ready handler - setup event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Setup event listeners for controls
    setupEventListeners();
    
    // Add scroll listener for infinite scroll
    const container = document.getElementById('chat-container');
    if (!container) {
        return;
    }
    container.addEventListener('scroll', handleScroll);
    
    // Load initial page
    if (window.config && typeof window.config.currentPage !== 'undefined') {
        loadPage(window.config.currentPage);
    } else {
        console.error('No config found or invalid current page');
    }
});

function handleScroll(e) {
    const container = e.target;
    
    if (window.isLoading) {
        // Don't initiate loads while a load is in progress
        return;
    }

    // Debounce heavy scroll handling to avoid spamming loads while user scrolls fast
    if (window._scrollDebounceTimer) {
        clearTimeout(window._scrollDebounceTimer);
    }
    window._scrollDebounceTimer = setTimeout(() => {
        const remainingToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
        const ratioToBottom = remainingToBottom / Math.max(1, container.scrollHeight);

        const shouldLoadNext = (remainingToBottom <= window.scrollLoadThresholdPx) || (ratioToBottom <= window.scrollLoadThresholdRatio);
        if (shouldLoadNext) {
            const nextPage = Math.max(...Array.from(window.loadedPages), 0) + 1;
            if (!window.loadedPages.has(nextPage) && window.hasMoreMessages) {
                loadPage(nextPage, document.getElementById('search-box').value, null, 'append');
            }
        }

        // previous (prepend) when near top
        const shouldLoadPrev = container.scrollTop <= window.scrollLoadThresholdPx || (container.scrollTop / Math.max(1, container.scrollHeight) <= window.scrollLoadThresholdRatio);
        if (shouldLoadPrev) {
            const prevPage = Math.min(...Array.from(window.loadedPages), 0) - 1;
            if (prevPage >= 0 && !window.loadedPages.has(prevPage)) {
                const oldScrollHeight = container.scrollHeight;
                const oldScrollTop = container.scrollTop;
                loadPage(prevPage, document.getElementById('search-box').value, null, 'prepend')
                    .then(() => {
                        // Maintain scroll position
                        const heightDiff = container.scrollHeight - oldScrollHeight;
                        container.scrollTop = oldScrollTop + heightDiff;
                    });
            }
        }
    }, window.scrollLoadDebounceMs);
}


function setupEventListeners() {
    // Enable debugging
    window.onerror = function(msg, url, line) {
        console.error(`Error: ${msg}\nAt: ${url}:${line}`);
        return false;
    };
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
        window.config.batchSize = parseInt(this.value, 10) || window.config.batchSize;
        loadPage(0, document.getElementById('search-box').value);
    });

    // Infinite scroll handling with scroll position preservation
    document.getElementById('chat-container').addEventListener('scroll', function(e) {
        const container = e.target;
        
        // Debug scroll information
        console.log('Scroll event:', {
            scrollHeight: container.scrollHeight,
            scrollTop: container.scrollTop,
            clientHeight: container.clientHeight,
            remainingToBottom: container.scrollHeight - container.scrollTop - container.clientHeight,
            loadedPages: Array.from(loadedPages),
            isLoading: isLoading
        });
        
        if (isLoading) {
            console.log('Skip loading - already in progress');
            return;
        }
        
        // Load next batch if near bottom (200px threshold)
        const remainingToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
        if (remainingToBottom < 200) {
            console.log('Near bottom, attempting to load next page');
            const loadedPagesArray = Array.from(loadedPages);
            if (loadedPagesArray.length === 0) {
                console.log('No pages loaded yet, loading page 0');
                loadPage(0, document.getElementById('search-box').value, null, 'append');
                return;
            }
            
            let nextPage = Math.max(...loadedPagesArray) + 1;
            console.log('Next page to load:', nextPage);
            if (!loadedPages.has(nextPage) && hasMoreMessages) {
                console.log('Loading next page:', nextPage);
                loadPage(nextPage, document.getElementById('search-box').value, null, 'append');
            }
        }
        
        // Load previous batch if near top (200px threshold)
        if (container.scrollTop < 200) {
            console.log('Near top, attempting to load previous page');
            const loadedPagesArray = Array.from(loadedPages);
            if (loadedPagesArray.length === 0) {
                return;
            }
            
            let prevPage = Math.min(...loadedPagesArray) - 1;
            console.log('Previous page to load:', prevPage);
            if (prevPage >= 0 && !loadedPages.has(prevPage)) {
                const oldScrollHeight = container.scrollHeight;
                const oldScrollTop = container.scrollTop;
                loadPage(prevPage, document.getElementById('search-box').value, null, 'prepend')
                    .then(() => {
                        // Adjust scroll position to maintain the same view when prepending
                        const newScrollHeight = container.scrollHeight;
                        const heightDiff = newScrollHeight - oldScrollHeight;
                        container.scrollTop = oldScrollTop + heightDiff;
                    });
            }
        }
    });
}

function loadPage(page, query = '', scrollToIndex = null, mode = 'replace') {
    if (window.isLoading) {
        return Promise.resolve();
    }
    
    if (window.loadedPages.has(page)) {
        return Promise.resolve();
    }
    
    if (!window.hasMoreMessages && mode === 'append') {
        return Promise.resolve();
    }
    
    window.isLoading = true;
    
    // Show loading indicator
    const container = document.getElementById('chat-container');
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading-indicator';
    loadingDiv.textContent = 'Loading messages...';
    loadingDiv.style.cssText = 'text-align: center; padding: 10px; color: #00a884;';
    
    if (mode === 'append') {
        container.appendChild(loadingDiv);
    } else if (mode === 'prepend') {
        container.insertBefore(loadingDiv, container.firstChild);
    }
    
    const url = `/api/messages?page=${page}&query=${encodeURIComponent(query)}&file=${window.config.encodedFile}&batch_size=${window.config.batchSize}`;
    return fetch(url)
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
                window.loadedPages = new Set([page]);
                window.totalLoadedMessages = data.total_matches;
            } else if (mode === 'append') {
                if (data.html && data.html.trim()) {
                    container.insertAdjacentHTML('beforeend', data.html);
                    window.loadedPages.add(page);
                    window.totalLoadedMessages += window.config.batchSize;
                } else {
                    window.hasMoreMessages = false;
                }
            } else if (mode === 'prepend') {
                if (data.html && data.html.trim()) {
                    container.insertAdjacentHTML('afterbegin', data.html);
                    window.loadedPages.add(page);
                    window.totalLoadedMessages += window.config.batchSize;
                }
            }
            
            renderPagination(page, data.total_matches);
            populateSenderDropdown(data.senders || []);
            applyMessageAlignment();
            
            // Remove loading indicator if it exists
            const loadingIndicator = container.querySelector('.loading-indicator');
            if (loadingIndicator) {
                loadingIndicator.remove();
            }
            
            window.isLoading = false;
            
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
            // Remove loading indicator if it exists
            const loadingIndicator = container.querySelector('.loading-indicator');
            if (loadingIndicator) {
                loadingIndicator.remove();
            }
            window.isLoading = false;
        });
}

function renderPagination(page, totalMatches) {
    const totalPages = Math.ceil(totalMatches / window.config.batchSize);
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
                    if (name === window.myName) {
                        opt.selected = true;
            }
            select.appendChild(opt);
        });
    }
}

function applyMessageAlignment() {
    window.myName = document.getElementById('my-name').value;
    try { localStorage.setItem('whatsapp_my_name_' + window.config.encodedFile, window.myName); } catch (e) {}

    document.querySelectorAll('.message').forEach(msgDiv => {
        const senderElem = msgDiv.querySelector('.sender');
        const senderName = senderElem ? senderElem.textContent : null;
        msgDiv.classList.remove('sent', 'received');
        if (window.myName && senderName === window.myName) {
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
    fetch(`/api/find?file=${window.config.encodedFile}&q=${encodeURIComponent(q)}`)
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
    const pageToLoad = Math.floor(globalIndex / window.config.batchSize);
    const queryVal = document.getElementById('search-box').value || '';
    loadPage(pageToLoad, queryVal, globalIndex);
}