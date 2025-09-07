// Глобальные переменные для хранения состояния
const state = {
    gameId: null,
    playerTokens: [],
    sockets: [null, null, null, null],
    connected: [false, false, false, false]
};

// Элементы UI
const startGameBtn = document.getElementById('startGameBtn');
const gameIdElement = document.getElementById('gameId');
const gameStatusElement = document.getElementById('gameStatus');
const statusElements = [
    document.getElementById('status1'),
    document.getElementById('status2'),
    document.getElementById('status3'),
    document.getElementById('status4')
];
const outputElements = [
    document.getElementById('output1'),
    document.getElementById('output2'),
    document.getElementById('output3'),
    document.getElementById('output4')
];
const inputElements = [
    document.getElementById('input1'),
    document.getElementById('input2'),
    document.getElementById('input3'),
    document.getElementById('input4')
];
const treeElements = [
    document.getElementById('json-tree-1'),
    document.getElementById('json-tree-2'),
    document.getElementById('json-tree-3'),
    document.getElementById('json-tree-4')
];

// Легковесная функция для создания JSON дерева
function createJsonTree(data, container) {
    container.innerHTML = '';
    
    // Рекурсивная функция для создания узлов дерева
    function createNode(value, key = null, isLast = true) {
        const node = document.createElement('div');
        node.className = 'node';
        
        const type = typeof value;
        const isArray = Array.isArray(value);
        const isObject = value !== null && type === 'object' && !isArray;
        
        if (isObject || isArray) {
            // Создаем узел для объекта или массива
            const toggle = document.createElement('span');
            toggle.className = 'toggle';
            toggle.textContent = '+';
            toggle.addEventListener('click', function(e) {
                e.stopPropagation();
                node.classList.toggle('expanded');
                node.classList.toggle('collapsed');
                toggle.textContent = node.classList.contains('expanded') ? '-' : '+';
            });
            
            const bracket = document.createElement('span');
            bracket.className = 'bracket';
            bracket.textContent = isArray ? '[' : '{';
            
            const children = document.createElement('div');
            children.className = 'children';
            
            // Добавляем дочерние элементы
            const entries = isArray ? 
                value.map((v, i) => [i, v]) : 
                Object.entries(value);
            
            entries.forEach(([k, v], i) => {
                const childNode = createNode(v, k, i === entries.length - 1);
                children.appendChild(childNode);
            });
            
            const closingBracket = document.createElement('span');
            closingBracket.className = 'bracket';
            closingBracket.textContent = isArray ? ']' : '}';
            
            if (key !== null) {
                const keySpan = document.createElement('span');
                keySpan.className = 'key';
                keySpan.textContent = `"${key}": `;
                
                node.appendChild(toggle);
                node.appendChild(keySpan);
                node.appendChild(bracket);
            } else {
                node.appendChild(toggle);
                node.appendChild(bracket);
            }
            
            node.appendChild(children);
            node.appendChild(closingBracket);
            
            if (!isLast) {
                const separator = document.createElement('span');
                separator.className = 'separator';
                separator.textContent = ',';
                node.appendChild(separator);
            }
            
            // Изначально сворачиваем узлы
            node.classList.add('collapsed');
        } else {
            // Создаем узел для примитивного значения
            const valueSpan = document.createElement('span');
            
            if (key !== null) {
                const keySpan = document.createElement('span');
                keySpan.className = 'key';
                keySpan.textContent = `"${key}": `;
                node.appendChild(keySpan);
            }
            
            if (type === 'string') {
                valueSpan.className = 'value-string';
                valueSpan.textContent = `"${value}"`;
            } else if (type === 'number') {
                valueSpan.className = 'value-number';
                valueSpan.textContent = value;
            } else if (type === 'boolean') {
                valueSpan.className = 'value-boolean';
                valueSpan.textContent = value;
            } else if (value === null) {
                valueSpan.className = 'value-null';
                valueSpan.textContent = 'null';
            }
            
            node.appendChild(valueSpan);
            
            if (!isLast) {
                const separator = document.createElement('span');
                separator.className = 'separator';
                separator.textContent = ',';
                node.appendChild(separator);
            }
        }
        
        return node;
    }
    
    const rootNode = createNode(data);
    container.appendChild(rootNode);
}

// Обработчик кнопки "Start Game"
startGameBtn.addEventListener('click', async () => {
    startGameBtn.disabled = true;
    gameStatusElement.textContent = "Starting...";
    
    try {
        // 1. Создаем игру
        const gameResponse = await fetch('http://localhost:8000/games', {
            method: 'POST'
        });
        
        if (!gameResponse.ok) {
            throw new Error(`HTTP error! status: ${gameResponse.status}`);
        }
        
        const gameData = await gameResponse.json();
        state.gameId = gameData.id;
        gameIdElement.textContent = state.gameId;
        gameStatusElement.textContent = "Game created";
        
        // 2. Присоединяем 4 игроков
        for (let i = 0; i < 4; i++) {
            try {
                const joinResponse = await fetch(`http://localhost:8000/games/${state.gameId}/join`, {
                    method: 'POST'
                });
                
                if (!joinResponse.ok) {
                    throw new Error(`HTTP error! status: ${joinResponse.status}`);
                }
                
                const joinData = await joinResponse.json();
                state.playerTokens[i] = joinData.token;
                
                outputElements[i].textContent += `Player token: ${state.playerTokens[i]}\n`;
                gameStatusElement.textContent = `Player ${i+1} joined`;
            } catch (error) {
                console.error(`Error joining player ${i+1}:`, error);
                outputElements[i].textContent += `Error: ${error.message}\n`;
            }
        }
        
        // 3. Запускаем игру
        const startResponse = await fetch(`http://localhost:8000/games/${state.gameId}/start`, {
            method: 'POST'
        });
        
        if (!startResponse.ok) {
            throw new Error(`HTTP error! status: ${startResponse.status}`);
        }
        
        gameStatusElement.textContent = "Game started";
        
        // 4. Устанавливаем WebSocket соединения
        for (let i = 0; i < 4; i++) {
            setupWebSocket(i);
        }
        
    } catch (error) {
        console.error("Error starting game:", error);
        gameStatusElement.textContent = `Error: ${error.message}`;
    } finally {
        startGameBtn.disabled = false;
    }
});

// Функция установки WebSocket соединения
function setupWebSocket(playerIndex) {
    if (state.sockets[playerIndex]) {
        state.sockets[playerIndex].close();
    }
    
    const wsUrl = `ws://localhost:8000/ws/${state.gameId}/player/${state.playerTokens[playerIndex]}`;
    const socket = new WebSocket(wsUrl);
    state.sockets[playerIndex] = socket;
    
    socket.onopen = () => {
        state.connected[playerIndex] = true;
        statusElements[playerIndex].textContent = "Connected";
        statusElements[playerIndex].className = "status connected";
        outputElements[playerIndex].textContent += "WebSocket connected\n";
    };
    
    socket.onmessage = (event) => {
        try {
            // Парсим входящие данные
            const data = JSON.parse(event.data);
            const formatted = JSON.stringify(data, null, 2);
            outputElements[playerIndex].textContent += `Received: ${formatted}\n`;
            
            // Обновляем дерево JSON
            createJsonTree(data, treeElements[playerIndex]);
            
            // Автопрокрутка к новому сообщению
            outputElements[playerIndex].scrollTop = outputElements[playerIndex].scrollHeight;
        } catch (e) {
            outputElements[playerIndex].textContent += `Received: ${event.data}\n`;
            treeElements[playerIndex].textContent = "Non-JSON response";
        }
    };
    
    socket.onclose = () => {
        state.connected[playerIndex] = false;
        statusElements[playerIndex].textContent = "Disconnected";
        statusElements[playerIndex].className = "status disconnected";
        outputElements[playerIndex].textContent += "WebSocket disconnected\n";
    };
    
    socket.onerror = (error) => {
        outputElements[playerIndex].textContent += `WebSocket error: ${error}\n`;
    };
}

// Функция отправки сообщения
function sendMessage(playerIndex) {
    if (!state.connected[playerIndex]) {
        outputElements[playerIndex].textContent += "Not connected to WebSocket\n";
        return;
    }
    
    try {
        const message = inputElements[playerIndex].value;
        
        // Парсим и снова строкифицируем, чтобы убедиться в валидности JSON
        const parsedMessage = JSON.parse(message);
        const stringMessage = JSON.stringify(parsedMessage);
        
        state.sockets[playerIndex].send(stringMessage);
        outputElements[playerIndex].textContent += `Sent: ${stringMessage}\n`;
        
        // Автопрокрутка к новому сообщению
        outputElements[playerIndex].scrollTop = outputElements[playerIndex].scrollHeight;
    } catch (error) {
        outputElements[playerIndex].textContent += `Error sending message: ${error.message}\n`;
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Добавляем обработчики для кнопок отправки
    document.querySelectorAll('button[data-player]').forEach(button => {
        const playerIndex = parseInt(button.getAttribute('data-player'));
        button.addEventListener('click', () => sendMessage(playerIndex));
    });
    
    // Добавляем обработчики для отправки по Enter (с зажатым Ctrl)
    inputElements.forEach((input, index) => {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) {
                sendMessage(index);
                e.preventDefault();
            }
        });
    });
    
    // Инициализируем JSON деревья с пустыми данными
    treeElements.forEach(element => {
        element.textContent = "No data received yet";
    });
});