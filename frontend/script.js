document.addEventListener('DOMContentLoaded', () => {
    const initialSections = document.getElementById('initial-sections');
    const currentChatContainer = document.getElementById('current-chat-container');
    const chatMessagesDisplay = document.getElementById('chat-messages-display');
    const userQuestionTextarea = document.getElementById('userQuestion');
    const submitBtn = document.getElementById('submitBtn');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    const newChatSidebarButton = document.getElementById('start-new-conversation-sidebar');
    const spinner = document.getElementById('spinner');
    const fileSpinner = document.getElementById('fileSpinner');

    // File Upload Elements
    const dragAndDropArea = document.getElementById('drag-and-drop-area');
    const fileInput = document.getElementById('fileInput');
    const fileChosenSpan = document.getElementById('file-chosen');
    const fileQuestionInput = document.getElementById('fileQuestion');
    const fileSubmitBtn = document.getElementById('fileSubmitBtn');
    const clearBtn = document.getElementById('clearBtn');

    let currentFile = null; // To store the selected file

    // --- Core Chat Functionality ---

    // Function to add a message to the chat display
    const addMessage = (content, type) => {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-bubble', type);
        messageDiv.innerHTML = content; // Use innerHTML to render formatted AI responses
        chatMessagesDisplay.appendChild(messageDiv);
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight; // Auto-scroll to bottom
    };

    // Function to handle sending a text message
    const sendTextMessage = async (question) => {
        if (!question.trim()) return;

        showChatArea(); // Ensure chat area is visible
        addMessage(`<p>${question}</p>`, 'user-query');
        userQuestionTextarea.value = ''; // Clear initial input field
        chatInput.value = ''; // Clear persistent chat input field

        spinner.style.display = 'block'; // Show general spinner
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight; // Scroll to spinner

        try {
            // Simulate AI response (replace with actual API call)
            // This is where you would send the 'question' to your backend AI
            const aiResponse = await simulateAIResponse(question); // Call a function that simulates/fetches AI response

            spinner.style.display = 'none'; // Hide spinner

            // Add AI response. If it contains law articles, render them.
            if (aiResponse.articles && aiResponse.articles.length > 0) {
                addMessage(formatAiResponseWithArticles(aiResponse.text, aiResponse.articles), 'ai-response');
                // You might want to automatically expand the first article or have a "show all" button
            } else {
                addMessage(`<p>${aiResponse.text}</p>`, 'ai-response');
            }

        } catch (error) {
            console.error('Error fetching AI response:', error);
            spinner.style.display = 'none';
            addMessage('<p class="error-message">Произошла ошибка при получении ответа. Пожалуйста, попробуйте еще раз.</p>', 'ai-response');
        }
    };

    // --- AI Response Simulation (Replace with actual backend API call) ---
    const simulateAIResponse = async (question) => {
        // Simulate network delay
        await new Promise(resolve => setTimeout(Math.random() * 2000 + 1000, resolve)); // 1-3 seconds delay

        // Example AI logic:
        let responseText = `<p>По вашему запросу: "${question}".</p>`;
        const lowerCaseQuestion = question.toLowerCase();
        let relevantArticles = [];

        if (lowerCaseQuestion.includes('многодетной семьи') || lowerCaseQuestion.includes('пособия')) {
            responseText += `<p>Чтобы я мог предоставить вам точную информацию о выплатах для многодетных семей, пожалуйста, уточните следующие детали:</p>
                <ul>
                    <li>В каком <strong>регионе Казахстана</strong> вы проживаете? (Например, город Алматы, Астана, Шымкент, или конкретная область?)</li>
                    <li><strong>Сколько детей</strong> в вашей семье, и каков <strong>возраст каждого ребенка</strong>?</li>
                    <li>Вы являетесь <strong>работающей</strong> матерью или <strong>неработающей</strong>?</li>
                </ul>
                <p>Эти данные помогут мне рассчитать точный размер пособий, исходя из актуального законодательства Республики Казахстан.</p>`;
            
            relevantArticles = [
                {
                    title: "Социальный кодекс: Статья 91. Размер пособия многодетной семье",
                    text: "Пособие многодетной семье выплачивается ежемесячно за счет бюджетных средств в следующих размерах: на четверых детей – 16,03 месячного расчетного показателя; на пятерых детей – 20,04 месячного расчетного показателя; на шестерых детей – 24,05 месячного расчетного показателя; на семерых детей – 28,06 месячного расчетного показателя, а на восьмерых и более детей – 4 месячных расчетных показателя на каждого ребенка.",
                    source: "Законодательство РК",
                    link: "#" // Replace with actual link
                }
            ];
        } else if (lowerCaseQuestion.includes('алматы') && lowerCaseQuestion.includes('4 ребенка') && lowerCaseQuestion.includes('работаю')) {
            responseText = `<p>Отлично, спасибо за уточнение! Исходя из того, что вы живете в Алматы, у вас 4 детей и вы работаете, вы имеете право на следующие выплаты согласно законодательству Республики Казахстан:</p>
                <ol>
                    <li>
                        <strong>Ежемесячное государственное пособие многодетным семьям:</strong>
                        <p>Для семей с 4 детьми размер пособия составляет <strong>16,03 месячных расчетных показателя (МРП)</strong>. На 2024 год, 1 МРП равен 3 692 тенге (для примера), соответственно, выплата составит 59 181.16 тенге.</p>
                        <small>(*Примечание: МРП утверждается ежегодно, точную сумму на текущий год рекомендую уточнить в официальных источниках или на egov.kz).</small>
                    </li>
                    <li>
                        <strong>Пособие по рождению ребенка (единовременное):</strong>
                        <p>Вы могли получить это пособие при рождении каждого ребенка. Для первого, второго и третьего ребенка это 38 МРП, для четвертого и последующих детей — 63 МРП.</p>
                    </li>
                    <li>
                        <strong>Выплаты по уходу за ребенком до достижения им одного года:</strong>
                        <p>Поскольку вы работаете, эти выплаты осуществляются из Государственного фонда социального страхования (ГФСС) в размере 40% от среднемесячного дохода за последние 24 месяца.</p>
                    </li>
                </ol>
                <p>Для оформления или проверки начислений этих пособий вам необходимо будет предоставить следующие документы в Департамент Комитета труда и социальной защиты по городу Алматы или через портал "Электронное правительство" (egov.kz):</p>
                <ul>
                    <li>Удостоверение личности одного из родителей (оригинал для сверки, копия);</li>
                    <li>Свидетельства о рождении всех детей (оригиналы для сверки, копии);</li>
                    <li>Справка о составе семьи (для подтверждения факта многодетности);</li>
                    <li>Справка с места работы (для работающих граждан);</li>
                    <li>Банковский счет для начисления пособий.</li>
                </ul>
                <p>Я могу помочь вам найти ближайшее отделение социальной защиты в Алматы, если потребуется, или дать ссылки на соответствующие разделы egov.kz.</p>`;
             relevantArticles = [
                {
                    title: "Социальный кодекс: Статья 91. Размер пособия многодетной семье",
                    text: "Пособие многодетной семье выплачивается ежемесячно за счет бюджетных средств в следующих размерах: на четверых детей – 16,03 месячного расчетного показателя; на пятерых детей – 20,04 месячного расчетного показателя; на шестерых детей – 24,05 месячного расчетного показателя; на семерых детей – 28,06 месячного расчетного показателя, а на восьмерых и более детей – 4 месячных расчетных показателя на каждого ребенка.",
                    source: "Законодательство РК",
                    link: "#" // Replace with actual link
                },
                {
                    title: "Закон РК О государственных пособиях семьям, имеющим детей",
                    text: "Настоящий Закон устанавливает виды государственных пособий семьям, имеющим детей, условия их назначения, размеры и порядок выплаты в Республике Казахстан.",
                    source: "Законодательство РК",
                    link: "#"
                }
            ];
        }
        else if (lowerCaseQuestion.includes('уволили без предупреждения')) {
            responseText = `<p>Если вас уволили без предупреждения, это может быть нарушением Трудового кодекса Республики Казахстан. Важно установить, по какой причине вас уволили и был ли соблюден порядок прекращения трудового договора.</p>
                <p>Согласно <strong>Трудовому кодексу РК</strong>, работодатель обязан соблюдать определенные процедуры при расторжении трудового договора. В зависимости от основания увольнения (например, ликвидация организации, сокращение штата, дисциплинарное взыскание) предусмотрены разные сроки уведомления и выплаты компенсаций.</p>
                <p>Для более точной консультации мне нужно знать:</p>
                <ul>
                    <li><strong>Какова официальная причина вашего увольнения, указанная в приказе?</strong></li>
                    <li><strong>Какой у вас был трудовой договор (срочный, бессрочный)?</strong></li>
                    <li><strong>Какова была ваша должность и стаж работы?</strong></li>
                </ul>
                <p>На основе этой информации я смогу подсказать, какие статьи Трудового кодекса применимы в вашей ситуации и как вы можете защитить свои права.</p>`;
            relevantArticles = [
                {
                    title: "Трудовой кодекс РК: Статья 52. Основания прекращения трудового договора по инициативе работодателя",
                    text: "Трудовой договор с работником по инициативе работодателя может быть прекращен в случаях...",
                    source: "Законодательство РК",
                    link: "#"
                },
                {
                    title: "Трудовой кодекс РК: Статья 53. Порядок прекращения трудового договора",
                    text: "Порядок прекращения трудового договора, сроки уведомления и выплаты компенсаций.",
                    source: "Законодательство РК",
                    link: "#"
                }
            ];
        } else if (lowerCaseQuestion.includes('россия') || lowerCaseQuestion.includes('рф') || lowerCaseQuestion.includes('федеральный')) {
             responseText = `<p>Извините, я специализируюсь исключительно на законодательстве Республики Казахстан и не могу предоставить информацию по законам других стран, включая Российскую Федерацию. Моя база знаний ограничена официальными правовыми актами Казахстана.</p>
                            <p>Могу ли я помочь вам с вопросами по законодательству Казахстана?</p>`;
        }
        else {
            responseText = `<p>Я готов помочь вам с вашим вопросом. Пожалуйста, предоставьте больше деталей.</p>
                            <p>Если ваш вопрос связан с:</p>
                            <ul>
                                <li><strong>Социальными выплатами</strong>, укажите регион и категорию (многодетная семья, инвалидность и т.д.).</li>
                                <li><strong>Трудовыми спорами</strong>, опишите ситуацию (увольнение, задержка зарплаты, условия труда).</li>
                                <li><strong>Гражданскими вопросами</strong> (наследство, договор, собственность), укажите суть проблемы.</li>
                            </ul>
                            <p>Чем точнее будет ваш запрос, тем более релевантный ответ я смогу дать, опираясь на законодательство Республики Казахстан.</p>`;
        }

        return { text: responseText, articles: relevantArticles };
    };

    // Function to format AI response with articles
    const formatAiResponseWithArticles = (responseText, articles) => {
        let html = `<div>${responseText}</div>`; // Wrap main text
        if (articles && articles.length > 0) {
            html += `<div class="laws-container">
                        <h3 class="laws-header"><i class="fas fa-gavel"></i> Релевантные статьи законодательства РК <span class="article-count">(Только законы РК)</span></h3>
                        <div class="article-accordion">`;
            articles.forEach((article, index) => {
                html += `
                    <div class="accordion-item">
                        <div class="accordion-header" onclick="toggleAccordion(this)">
                            <span class="card-title">${index + 1}. ${article.title}</span>
                            <i class="fas fa-chevron-down accordion-icon"></i>
                        </div>
                        <div class="accordion-content">
                            <p class="card-body-text">${article.text}</p>
                            <div class="card-footer">
                                <span class="card-source">Источник: ${article.source}</span>
                                <a href="${article.link}" class="card-link" target="_blank">Читать полностью <i class="fas fa-external-link-alt"></i></a>
                            </div>
                        </div>
                    </div>`;
            });
            html += `</div></div>`;
        }
        return html;
    };

    // Function to toggle accordion
    // Make this a global function or attach to window for onclick to work from dynamically added HTML
    window.toggleAccordion = (element) => {
        const item = element.closest('.accordion-item');
        const content = item.querySelector('.accordion-content');
        const icon = element.querySelector('.accordion-icon');

        item.classList.toggle('active');
        if (item.classList.contains('active')) {
            content.style.maxHeight = content.scrollHeight + "px";
            icon.classList.replace('fa-chevron-down', 'fa-chevron-up');
        } else {
            content.style.maxHeight = "0";
            icon.classList.replace('fa-chevron-up', 'fa-chevron-down');
        }
    };


    // --- UI State Management ---

    // Function to switch to chat view
    const showChatArea = () => {
        initialSections.style.display = 'none';
        currentChatContainer.style.display = 'flex';
        chatInput.focus(); // Focus the new input field
    };

    // Function to switch to initial view
    const showInitialSections = () => {
        initialSections.style.display = 'flex';
        currentChatContainer.style.display = 'none';
        // Clear chat history when starting a new chat
        chatMessagesDisplay.innerHTML = '';
        userQuestionTextarea.value = '';
        fileQuestionInput.value = '';
        clearFileSelection();
    };

    // --- Event Listeners ---

    // Initial form submission handler
    submitBtn.addEventListener('click', (e) => {
        e.preventDefault();
        sendTextMessage(userQuestionTextarea.value);
    });

    // Persistent chat input handler
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { // Allow Shift+Enter for new line
            e.preventDefault();
            sendTextMessage(chatInput.value);
        }
    });

    sendButton.addEventListener('click', () => {
        sendTextMessage(chatInput.value);
    });

    // "New Chat" button in sidebar
    newChatSidebarButton.addEventListener('click', showInitialSections);

    // --- File Upload Logic ---

    // Highlight drag-and-drop area
    dragAndDropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dragAndDropArea.classList.add('highlight');
    });

    dragAndDropArea.addEventListener('dragleave', () => {
        dragAndDropArea.classList.remove('highlight');
    });

    dragAndDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dragAndDropArea.classList.remove('highlight');
        if (e.dataTransfer.files.length > 0) {
            handleFileSelection(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
        }
    });

    const handleFileSelection = (file) => {
        currentFile = file;
        fileChosenSpan.textContent = file.name;
        fileSubmitBtn.disabled = false;
        clearBtn.disabled = false;
        fileQuestionInput.focus(); // Focus on the question for the file
    };

    const clearFileSelection = () => {
        currentFile = null;
        fileInput.value = ''; // Clear input element
        fileChosenSpan.textContent = 'Файл не выбран';
        fileSubmitBtn.disabled = true;
        clearBtn.disabled = true;
        fileQuestionInput.value = ''; // Clear file question
    };

    clearBtn.addEventListener('click', clearFileSelection);

    fileSubmitBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (!currentFile) return;

        showChatArea(); // Ensure chat area is visible

        const fileQuestion = fileQuestionInput.value.trim();
        const userFileMessage = `<p><strong>Документ загружен:</strong> ${currentFile.name}</p>` +
                                (fileQuestion ? `<p><strong>Мой вопрос:</strong> ${fileQuestion}</p>` : '');
        addMessage(userFileMessage, 'user-query');

        fileSpinner.style.display = 'block'; // Show file spinner
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;

        try {
            // Simulate file analysis (replace with actual API call to send file)
            // In a real app, you'd send `currentFile` and `fileQuestion` to your backend.
            await new Promise(resolve => setTimeout(Math.random() * 3000 + 2000, resolve)); // 2-5 seconds delay

            fileSpinner.style.display = 'none';

            // Simulate AI response after file analysis
            const aiFileResponseText = `<p>ИИ-юрист успешно проанализировал документ "${currentFile.name}".</p>
                                        <p><strong>Резюме документа:</strong> (Здесь будет краткий обзор содержания файла).</p>
                                        <p><strong>Ключевые юридические аспекты:</strong> (Здесь будет извлеченная информация).</p>
                                        <p>Если у вас есть конкретный вопрос по этому документу, пожалуйста, задайте его.</p>`;
            addMessage(aiFileResponseText, 'ai-response');

            clearFileSelection(); // Clear file selection after processing
        } catch (error) {
            console.error('Error analyzing file:', error);
            fileSpinner.style.display = 'none';
            addMessage('<p class="error-message">Произошла ошибка при анализе документа. Пожалуйста, попробуйте еще раз.</p>', 'ai-response');
            clearFileSelection();
        }
    });

    // Initialize UI state
    showInitialSections(); // Start with initial sections visible
});
