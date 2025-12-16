/**
 * ALPACA RAG Test Console
 * Интерактивный фронтенд для тестирования RAG запросов с поддержкой SSE streaming
 */

class TestConsole {
    constructor() {
        this.queries = [...window.DEFAULT_QUERIES];
        this.results = [];
        this.isRunning = false;
        this.abortController = null;
        this.serverMode = false; // true если запущен через server.js
        
        this.initElements();
        this.initEventListeners();
        this.checkServerMode();
        this.loadBackends();
        this.renderQueries();
    }

    /**
     * Проверяем, запущены ли мы через server.js (есть API)
     */
    async checkServerMode() {
        try {
            const response = await fetch('/api/queries');
            if (response.ok) {
                this.serverMode = true;
                const data = await response.json();
                this.queries = data.queries;
                this.renderQueries();
                console.log('✅ Server mode: запросы загружены из файла');
            }
        } catch (e) {
            // Работаем без сервера - запросы только в памяти
            console.log('ℹ️ Static mode: изменения запросов не сохраняются');
        }
    }

    /**
     * Загружаем список доступных бэкендов с сервера
     */
    async loadBackends() {
        const apiUrl = this.apiUrlInput.value;
        // /api/chat → /api/backends
        const backendsUrl = apiUrl.replace(/\/api\/chat\/?$/, '/api/backends');
        
        try {
            const response = await fetch(backendsUrl);
            if (response.ok) {
                const data = await response.json();
                this.renderBackendOptions(data.available, data.default);
                console.log(`✅ Backends loaded: ${data.available.join(', ')} (default: ${data.default})`);
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (e) {
            console.warn('⚠️ Не удалось загрузить список бэкендов:', e.message);
            // Fallback на базовые значения
            this.renderBackendOptions(['simple', 'agent', 'complex_agent'], 'complex_agent');
        }
    }

    /**
     * Отрисовка опций бэкендов в select
     */
    renderBackendOptions(backends, defaultBackend) {
        this.backendSelect.innerHTML = backends
            .map(b => `<option value="${b}" ${b === defaultBackend ? 'selected' : ''}>${b}</option>`)
            .join('');
    }

    initElements() {
        // Config
        this.apiUrlInput = document.getElementById('apiUrl');
        this.backendSelect = document.getElementById('backend');
        
        // Query list
        this.queryList = document.getElementById('queryList');
        this.newQueryInput = document.getElementById('newQuery');
        this.addQueryBtn = document.getElementById('addQueryBtn');
        
        // Controls
        this.runAllBtn = document.getElementById('runAllBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.invertCheckboxesBtn = document.getElementById('invertCheckboxesBtn');
        
        // Manual query
        this.manualInput = document.getElementById('manualInput');
        this.sendBtn = document.getElementById('sendBtn');
        
        // Response display
        this.responseStatus = document.getElementById('responseStatus');
        this.responseMeta = document.getElementById('responseMeta');
        this.responseContent = document.getElementById('responseContent');
        this.responseSources = document.getElementById('responseSources');
        
        // Results
        this.resultsSummary = document.getElementById('resultsSummary');
        this.resultsBody = document.getElementById('resultsBody');
    }

    initEventListeners() {
        this.runAllBtn.addEventListener('click', () => this.runAllQueries());
        this.stopBtn.addEventListener('click', () => this.stopExecution());
        this.invertCheckboxesBtn.addEventListener('click', () => this.invertCheckboxes());
        this.addQueryBtn.addEventListener('click', () => this.addQuery());
        this.sendBtn.addEventListener('click', () => this.sendManualQuery());
        
        this.newQueryInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.addQuery();
        });
        
        this.manualInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendManualQuery();
            }
            // Shift+Enter — перенос строки (поведение по умолчанию)
        });

        // Перезагружать бэкенды при изменении API URL
        this.apiUrlInput.addEventListener('change', () => this.loadBackends());
    }

    renderQueries() {
        this.queryList.innerHTML = this.queries.map((query, index) => `
            <div class="query-item" data-index="${index}">
                <input type="checkbox" checked>
                <span class="query-text" title="${this.escapeHtml(query)}">${this.escapeHtml(query)}</span>
                <span class="query-delete" onclick="testConsole.deleteQuery(${index})">✕</span>
            </div>
        `).join('');
        
        // Add click handler for running single query
        this.queryList.querySelectorAll('.query-text').forEach((el, index) => {
            el.addEventListener('click', () => this.runSingleQuery(index));
        });
    }

    async addQuery() {
        const query = this.newQueryInput.value.trim();
        if (!query) return;
        
        if (this.serverMode) {
            try {
                const response = await fetch('/api/queries', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query })
                });
                if (response.ok) {
                    const data = await response.json();
                    this.queries = data.queries;
                    console.log(`✅ Запрос сохранён в файл: "${query}"`);
                } else {
                    throw new Error('Ошибка сохранения');
                }
            } catch (error) {
                console.error('Ошибка добавления:', error);
                this.showError('Не удалось сохранить запрос');
                return;
            }
        } else {
            this.queries.push(query);
        }
        
        this.newQueryInput.value = '';
        this.renderQueries();
    }

    async deleteQuery(index) {
        const query = this.queries[index];
        
        if (this.serverMode) {
            try {
                const response = await fetch(`/api/queries/${index}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    const data = await response.json();
                    this.queries = data.queries;
                    console.log(`🗑️ Запрос удалён из файла: "${query}"`);
                } else {
                    throw new Error('Ошибка удаления');
                }
            } catch (error) {
                console.error('Ошибка удаления:', error);
                this.showError('Не удалось удалить запрос');
                return;
            }
        } else {
            this.queries.splice(index, 1);
        }
        
        this.renderQueries();
    }

    async runAllQueries() {
        if (this.isRunning) return;
        
        this.isRunning = true;
        this.runAllBtn.disabled = true;
        this.stopBtn.disabled = false;
        this.abortController = new AbortController();
        
        const checkedItems = this.queryList.querySelectorAll('.query-item input:checked');
        const indices = Array.from(checkedItems).map(cb => 
            parseInt(cb.closest('.query-item').dataset.index)
        );
        
        for (const index of indices) {
            if (!this.isRunning) break;
            await this.runSingleQuery(index, true);
        }
        
        this.isRunning = false;
        this.runAllBtn.disabled = false;
        this.stopBtn.disabled = true;
        this.updateSummary();
    }

    stopExecution() {
        this.isRunning = false;
        if (this.abortController) {
            this.abortController.abort();
        }
        this.runAllBtn.disabled = false;
        this.stopBtn.disabled = true;
    }

    async runSingleQuery(index, isBatch = false) {
        const query = this.queries[index];
        const queryItem = this.queryList.querySelector(`[data-index="${index}"]`);
        
        if (queryItem) {
            queryItem.classList.add('running');
            queryItem.classList.remove('success');
        }
        
        const startTime = Date.now();
        
        try {
            const result = await this.executeQuery(query);
            result.index = index;
            result.query = query;
            result.duration = Date.now() - startTime;
            
            this.results.push(result);
            this.addResultRow(result);
            
            if (queryItem) {
                queryItem.classList.remove('running');
                queryItem.classList.add('success');
            }
        } catch (error) {
            const errorResult = {
                index,
                query,
                duration: Date.now() - startTime,
                error: error.message,
                filters: {},
                found: 0,
                answer: `Ошибка: ${error.message}`
            };
            this.results.push(errorResult);
            this.addResultRow(errorResult);
            
            if (queryItem) {
                queryItem.classList.remove('running');
            }
        }
        
        if (!isBatch) {
            this.updateSummary();
        }
    }

    async sendManualQuery() {
        const query = this.manualInput.value.trim();
        if (!query) return;
        
        this.sendBtn.disabled = true;
        
        try {
            await this.executeQuery(query);
        } catch (error) {
            this.showError(error.message);
        }
        
        this.sendBtn.disabled = false;
    }

    async executeQuery(query) {
        const apiUrl = this.apiUrlInput.value;
        const backend = this.backendSelect.value;
        
        // Reset display
        this.responseStatus.textContent = 'streaming...';
        this.responseStatus.className = 'streaming';
        this.responseMeta.innerHTML = '';
        this.responseContent.textContent = '';
        this.responseSources.innerHTML = '';
        
        const result = {
            filters: {},
            found: 0,
            answer: '',
            sources: [],
            searchMessages: [],
            backend: null,
            ttft: null
        };
        
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: query, backend }),
            signal: this.abortController?.signal
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    const eventType = line.slice(7);
                    continue;
                }
                
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (!data || data === '{}') continue;
                    
                    try {
                        const parsed = JSON.parse(data);
                        this.handleStreamEvent(parsed, result);
                    } catch (e) {
                        // Skip invalid JSON
                    }
                }
            }
        }
        
        // Финальный статус с backend и TTFT
        let doneText = '✅ done';
        if (result.backend) {
            doneText = `✅ ${result.backend}`;
        }
        if (result.ttft !== null) {
            doneText += ` | TTFT: ${result.ttft}s`;
        }
        this.responseStatus.textContent = doneText;
        this.responseStatus.className = 'done';
        
        return result;
    }

    handleStreamEvent(data, result) {
        // Timing info (backend + TTFT)
        if (data.backend !== undefined || data.ttft !== undefined) {
            if (data.backend) result.backend = data.backend;
            if (data.ttft !== undefined) result.ttft = data.ttft;
            this.updateTimingDisplay(result);
        }
        
        // Tool call (search status)
        if (data.name === 'search_status') {
            result.searchMessages.push(data.message);
            this.updateMeta(data.message, result);
            
            // Parse found count
            const foundMatch = data.message.match(/Найдено (\d+)/);
            if (foundMatch) {
                result.found = parseInt(foundMatch[1]);
            }
            
            // Parse filters from message
            this.parseFiltersFromMessage(data.message, result);
        }
        
        // Metadata (sources)
        if (data.sources) {
            result.sources = data.sources;
            this.renderSources(data.sources);
        }
        
        // Content chunk
        if (data.content !== undefined) {
            result.answer += data.content;
            this.responseContent.textContent = result.answer;
            this.responseContent.scrollTop = this.responseContent.scrollHeight;
        }
    }

    parseFiltersFromMessage(message, result) {
        // Parse category
        const catMatch = message.match(/категории «([^»]+)»/);
        if (catMatch) result.filters.category = catMatch[1];
        
        // Parse entity
        const entityMatch = message.match(/упоминанием «([^»]+)»/);
        if (entityMatch) result.filters.entity = entityMatch[1];
        
        // Parse date range
        const dateMatch = message.match(/период (\d{4}-\d{2}-\d{2}) — (\d{4}-\d{2}-\d{2})/);
        if (dateMatch) {
            result.filters.date_from = dateMatch[1];
            result.filters.date_to = dateMatch[2];
        }
        
        // Parse keywords
        const kwMatch = message.match(/ключевым словам: ([^.]+)/);
        if (kwMatch) result.filters.keywords = kwMatch[1].split(', ');
    }

    updateMeta(message, result) {
        let html = `<div>🔎 ${message}</div>`;
        
        if (Object.keys(result.filters).length > 0) {
            html += '<div style="margin-top: 5px;">Фильтры: ';
            for (const [key, value] of Object.entries(result.filters)) {
                const displayValue = Array.isArray(value) ? value.join(', ') : value;
                html += `<span class="filter-tag">${key}: ${displayValue}</span>`;
            }
            html += '</div>';
        }
        
        this.responseMeta.innerHTML = html;
    }

    updateTimingDisplay(result) {
        // Обновляем статус с информацией о backend и TTFT
        let statusText = 'streaming';
        if (result.backend) {
            statusText = `⚙️ ${result.backend}`;
        }
        if (result.ttft !== null) {
            statusText += ` | TTFT: ${result.ttft}s`;
        }
        this.responseStatus.textContent = statusText;
        this.responseStatus.className = 'streaming';
    }

    renderSources(sources) {
        if (!sources || sources.length === 0) return;
        
        const html = `
            <details open>
                <summary>📎 Источники (${sources.length})</summary>
                ${sources.slice(0, 10).map(s => `
                    <div class="source-item clickable" onclick="testConsole.openSource('${this.escapeHtml(s.download_url || '')}', '${this.escapeHtml(s.file_path || '')}')">
                        <div class="source-header">
                            <strong>${this.escapeHtml(s.file_name || s.file_path)}</strong>
                            <span class="source-link">🔗</span>
                        </div>
                        <div class="source-path">${this.escapeHtml(s.file_path || '')}</div>
                        <div class="source-meta">
                            <span class="source-tag">${s.category || 'Без категории'}</span>
                            <span class="source-tag">chunk: ${s.chunk_index ?? '?'}</span>
                            <span class="source-tag ${this.getSimilarityClass(s.similarity)}">sim: ${s.similarity ? (s.similarity * 100).toFixed(1) + '%' : '?'}</span>
                            ${s.modified_at ? `<span class="source-tag">📅 ${this.formatDate(s.modified_at)}</span>` : ''}
                        </div>
                        ${s.title ? `<div class="source-title">📄 ${this.escapeHtml(s.title)}</div>` : ''}
                        ${s.summary ? `<div class="source-summary">${this.escapeHtml(s.summary)}</div>` : ''}
                    </div>
                `).join('')}
                ${sources.length > 10 ? `<div style="color: var(--text-secondary); padding: 5px;">...и ещё ${sources.length - 10}</div>` : ''}
            </details>
        `;
        
        this.responseSources.innerHTML = html;
    }

    getSimilarityClass(similarity) {
        if (!similarity) return '';
        if (similarity >= 0.7) return 'sim-high';
        if (similarity >= 0.5) return 'sim-medium';
        return 'sim-low';
    }

    formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
        } catch {
            return dateStr;
        }
    }

    openSource(downloadUrl, filePath) {
        if (downloadUrl) {
            window.open(downloadUrl, '_blank');
        } else if (filePath) {
            // Fallback: construct URL from file path
            const baseUrl = this.apiUrlInput.value.replace('/api/chat', '/api/files/download');
            const url = `${baseUrl}?path=${encodeURIComponent(filePath)}`;
            window.open(url, '_blank');
        }
    }

    addResultRow(result) {
        const rowIndex = this.results.length - 1;
        const row = document.createElement('tr');
        row.className = 'result-row';
        row.dataset.resultIndex = rowIndex;
        
        const filtersHtml = Object.entries(result.filters || {})
            .map(([k, v]) => `<span class="filter-tag">${k}: ${Array.isArray(v) ? v.join(', ') : v}</span>`)
            .join(' ') || '-';
        
        const answerPreview = (result.answer || '').replace(/\n/g, ' ').slice(0, 150);
        const hasDetails = result.sources?.length > 0 || result.answer?.length > 150;
        
        row.innerHTML = `
            <td class="expand-col">
                ${hasDetails ? `<button class="expand-btn" onclick="testConsole.toggleResultDetails(${rowIndex})">▶</button>` : ''}
            </td>
            <td>${result.index + 1}</td>
            <td class="query-col truncate" title="${this.escapeHtml(result.query)}">${this.escapeHtml(result.query)}</td>
            <td class="filters-col">${filtersHtml}</td>
            <td>${result.found || 0}</td>
            <td>${(result.duration / 1000).toFixed(1)}s</td>
            <td class="answer-col" title="${this.escapeHtml(result.answer || '')}">${this.escapeHtml(answerPreview)}${result.answer?.length > 150 ? '...' : ''}</td>
        `;
        
        if (result.error) {
            row.style.color = 'var(--error)';
        }
        
        this.resultsBody.appendChild(row);
        
        // Создаём скрытую строку с подробностями
        if (hasDetails) {
            const detailsRow = document.createElement('tr');
            detailsRow.className = 'result-details-row hidden';
            detailsRow.id = `details-${rowIndex}`;
            detailsRow.innerHTML = `<td colspan="7">${this.renderResultDetails(result)}</td>`;
            this.resultsBody.appendChild(detailsRow);
        }
    }

    toggleResultDetails(rowIndex) {
        const detailsRow = document.getElementById(`details-${rowIndex}`);
        const btn = this.resultsBody.querySelector(`tr[data-result-index="${rowIndex}"] .expand-btn`);
        
        if (detailsRow) {
            const isHidden = detailsRow.classList.toggle('hidden');
            if (btn) btn.textContent = isHidden ? '▶' : '▼';
        }
    }

    renderResultDetails(result) {
        let html = '<div class="result-details">';
        
        // Полный ответ
        if (result.answer) {
            html += `
                <div class="details-section">
                    <h4>💬 Полный ответ</h4>
                    <div class="details-answer">${this.escapeHtml(result.answer)}</div>
                </div>
            `;
        }
        
        // Источники
        if (result.sources && result.sources.length > 0) {
            html += `
                <div class="details-section">
                    <h4>📎 Найденные документы (${result.sources.length})</h4>
                    <div class="details-sources">
                        ${result.sources.map((s, i) => this.renderSourceCard(s, i)).join('')}
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        return html;
    }

    renderSourceCard(source, index) {
        const similarity = source.similarity ? (source.similarity * 100).toFixed(1) + '%' : '?';
        const simClass = this.getSimilarityClass(source.similarity);
        
        return `
            <div class="source-card">
                <div class="source-card-header">
                    <span class="source-num">#${index + 1}</span>
                    <strong class="source-name">${this.escapeHtml(source.file_name || source.file_path?.split('/').pop() || 'Документ')}</strong>
                    <span class="source-tag ${simClass}">sim: ${similarity}</span>
                    ${source.download_url ? `<button class="btn btn-small" onclick="testConsole.openSource('${this.escapeHtml(source.download_url)}', '')">📥 Открыть</button>` : ''}
                </div>
                <div class="source-card-path">${this.escapeHtml(source.file_path || '')}</div>
                <div class="source-card-meta">
                    ${source.category ? `<span class="source-tag">${source.category}</span>` : ''}
                    ${source.chunk_index !== undefined ? `<span class="source-tag">chunk: ${source.chunk_index}</span>` : ''}
                    ${source.modified_at ? `<span class="source-tag">📅 ${this.formatDate(source.modified_at)}</span>` : ''}
                </div>
                ${source.title ? `<div class="source-card-title">📄 ${this.escapeHtml(source.title)}</div>` : ''}
                ${source.summary ? `<div class="source-card-summary">${this.escapeHtml(source.summary)}</div>` : ''}
                ${source.content ? `<div class="source-card-content"><details><summary>Содержимое чанка</summary><pre>${this.escapeHtml(source.content)}</pre></details></div>` : ''}
            </div>
        `;
    }

    closeModal() {
        document.getElementById('documentModal').classList.remove('visible');
    }

    updateSummary() {
        const total = this.results.length;
        const success = this.results.filter(r => !r.error && r.found > 0).length;
        const errors = this.results.filter(r => r.error).length;
        const avgTime = total > 0 
            ? (this.results.reduce((sum, r) => sum + r.duration, 0) / total / 1000).toFixed(1) 
            : 0;
        
        this.resultsSummary.innerHTML = `
            <div class="stat"><span class="stat-value">${total}</span> всего</div>
            <div class="stat" style="color: var(--success)"><span class="stat-value">${success}</span> успешно</div>
            <div class="stat" style="color: var(--accent)"><span class="stat-value">${errors}</span> ошибок</div>
            <div class="stat"><span class="stat-value">${avgTime}s</span> среднее время</div>
        `;
    }

    invertCheckboxes() {
        this.queryList.querySelectorAll('.query-item input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = !checkbox.checked;
        });
    }

    showError(message) {
        this.responseStatus.textContent = 'error';
        this.responseStatus.className = 'error';
        this.responseContent.textContent = `Ошибка: ${message}`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
}

// Initialize
const testConsole = new TestConsole();
