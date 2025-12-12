/**
 * ALPACA Test Frontend Server
 * Node.js сервер для обслуживания статических файлов и CRUD операций с запросами
 * 
 * Запуск: node server.js
 * Порт: 8888 (или переменная окружения PORT)
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = process.env.PORT || 8888;
const QUERIES_FILE = path.join(__dirname, 'queries.js');

// MIME types для статических файлов
const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
};

/**
 * Читает запросы из queries.js
 */
function readQueries() {
    try {
        const content = fs.readFileSync(QUERIES_FILE, 'utf-8');
        // Парсим JS файл - ищем массив DEFAULT_QUERIES
        const match = content.match(/const DEFAULT_QUERIES = \[([\s\S]*?)\];/);
        if (!match) {
            console.error('Не удалось найти DEFAULT_QUERIES в файле');
            return [];
        }
        
        const arrayContent = match[1];
        const queries = [];
        
        // Парсим строки (учитываем комментарии)
        const lines = arrayContent.split('\n');
        for (const line of lines) {
            const trimmed = line.trim();
            // Пропускаем комментарии и пустые строки
            if (trimmed.startsWith('//') || trimmed === '' || trimmed === ',') continue;
            
            // Извлекаем строку в кавычках
            const strMatch = trimmed.match(/^["'](.+?)["'],?$/);
            if (strMatch) {
                queries.push(strMatch[1]);
            }
        }
        
        return queries;
    } catch (error) {
        console.error('Ошибка чтения queries.js:', error.message);
        return [];
    }
}

/**
 * Записывает запросы в queries.js
 */
function writeQueries(queries) {
    const content = `// Предзагруженные тестовые запросы
// Автоматически обновляется сервером при добавлении/удалении запросов
const DEFAULT_QUERIES = [
${queries.map(q => `    "${q.replace(/"/g, '\\"')}",`).join('\n')}
];

// Экспорт для использования в app.js
window.DEFAULT_QUERIES = DEFAULT_QUERIES;
`;
    
    fs.writeFileSync(QUERIES_FILE, content, 'utf-8');
}

/**
 * Обрабатывает API запросы
 */
async function handleApi(req, res, pathname) {
    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    
    if (req.method === 'OPTIONS') {
        res.writeHead(204);
        res.end();
        return;
    }
    
    // GET /api/queries - получить все запросы
    if (pathname === '/api/queries' && req.method === 'GET') {
        const queries = readQueries();
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ queries }));
        return;
    }
    
    // POST /api/queries - добавить запрос
    if (pathname === '/api/queries' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
            try {
                const { query } = JSON.parse(body);
                if (!query || typeof query !== 'string') {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'query is required' }));
                    return;
                }
                
                const queries = readQueries();
                queries.push(query.trim());
                writeQueries(queries);
                
                console.log(`✅ Добавлен запрос: "${query.trim()}"`);
                
                res.writeHead(201, { 'Content-Type': 'application/json; charset=utf-8' });
                res.end(JSON.stringify({ success: true, queries }));
            } catch (error) {
                res.writeHead(400, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: error.message }));
            }
        });
        return;
    }
    
    // DELETE /api/queries/:index - удалить запрос по индексу
    const deleteMatch = pathname.match(/^\/api\/queries\/(\d+)$/);
    if (deleteMatch && req.method === 'DELETE') {
        const index = parseInt(deleteMatch[1]);
        const queries = readQueries();
        
        if (index < 0 || index >= queries.length) {
            res.writeHead(404, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Query not found' }));
            return;
        }
        
        const deleted = queries.splice(index, 1)[0];
        writeQueries(queries);
        
        console.log(`🗑️ Удалён запрос [${index}]: "${deleted}"`);
        
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ success: true, deleted, queries }));
        return;
    }
    
    // 404 для неизвестных API endpoints
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
}

/**
 * Обрабатывает запросы статических файлов
 */
function handleStatic(req, res, pathname) {
    // Если корень, отдаём index.html
    if (pathname === '/') pathname = '/index.html';
    
    const filePath = path.join(__dirname, pathname);
    
    // Проверяем что путь не выходит за пределы директории
    if (!filePath.startsWith(__dirname)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
    }
    
    fs.readFile(filePath, (err, data) => {
        if (err) {
            if (err.code === 'ENOENT') {
                res.writeHead(404);
                res.end('Not Found');
            } else {
                res.writeHead(500);
                res.end('Server Error');
            }
            return;
        }
        
        const ext = path.extname(filePath).toLowerCase();
        const contentType = MIME_TYPES[ext] || 'application/octet-stream';
        
        res.writeHead(200, { 'Content-Type': contentType });
        res.end(data);
    });
}

// Создаём сервер
const server = http.createServer((req, res) => {
    const parsedUrl = url.parse(req.url);
    const pathname = parsedUrl.pathname;
    
    // API requests
    if (pathname.startsWith('/api/')) {
        handleApi(req, res, pathname);
        return;
    }
    
    // Static files
    handleStatic(req, res, pathname);
});

server.listen(PORT, () => {
    console.log(`
  ╔════════════════════════════════════════╗
  ║   ALPACA RAG Test Console Server       ║
  ╠════════════════════════════════════════╣
  ║   URL: http://127.0.0.1:${PORT}            ║
  ║                                        ║
  ║   API:                                 ║
  ║   GET    /api/queries     - список     ║
  ║   POST   /api/queries     - добавить   ║
  ║   DELETE /api/queries/:id - удалить    ║
  ╚════════════════════════════════════════╝
    `);
});
