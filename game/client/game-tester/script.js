// Глобальные переменные для хранения состояния
const state = {
    gameId: null,
    playerTokens: [],
    sockets: [null, null, null, null],
    connected: [false, false, false, false],
    playerData: [{}, {}, {}, {}] // Данные для каждого игрока
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

// Функция для получения данных игрока (используется json-tree.js)
function getPlayerData(playerIndex) {
    return {
        data: state.playerData[playerIndex]
    };
}

// Функция обновления JSON дерева
function updateJsonTree(playerIndex, data) {
    state.playerData[playerIndex] = data;
    
    // Переинициализируем дерево с новыми данными
    const treeElement = treeElements[playerIndex];
    treeElement.setAttribute('data-jsontree-js', `getPlayerData(${playerIndex})`);
    
    // Инициализируем json-tree
    if (window.JsonTree) {
        // Удаляем старый экземпляр, если есть
        if (treeElement._jsonTreeInstance) {
            treeElement._jsonTreeInstance.destroy();
        }
        
        // Создаем новый экземпляр
        treeElement._jsonTreeInstance = JsonTree.create(treeElement, {
            data: data
        });
    }
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
            console.log(`Received data: ${event.data}`)
            outputElements[playerIndex].textContent += `Received: ${formatted}\n`;
            
            // Обновляем дерево JSON
            updateJsonTree(playerIndex, data);
            
            // Автопрокрутка к новому сообщению
            outputElements[playerIndex].scrollTop = outputElements[playerIndex].scrollHeight;
        } catch (e) {
            outputElements[playerIndex].textContent += `Received: ${event.data}\n`;
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
    
    // Инициализируем json-tree для каждого игрока
    if (window.JsonTree) {
        treeElements.forEach((element, index) => {
            element._jsonTreeInstance = JsonTree.create(element, {
                data: state.playerData[index]
            });
        });
    }
});