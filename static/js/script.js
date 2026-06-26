document.addEventListener('DOMContentLoaded', function() {
    const tabLinks = document.querySelectorAll('.tabs a');
    const courseSections = document.querySelectorAll('.course-section');

    tabLinks.forEach(link => {
        link.addEventListener('click', function(event) {
            event.preventDefault();

            // Убираем класс 'active' со всех вкладок и секций
            tabLinks.forEach(tab => tab.classList.remove('active'));
            courseSections.forEach(section => section.classList.remove('active'));

            // Добавляем класс 'active' к текущей вкладке
            this.classList.add('active');

            // Показываем соответствующую секцию курсов
            const targetId = this.getAttribute('href');
            const targetSection = document.querySelector(targetId);
            if (targetSection) {
                targetSection.classList.add('active');
            }
        });
    });

    // Делаем первую вкладку активной по умолчанию
    document.querySelector('.tabs a').click();

    const hamburgerMenu = document.querySelector('.hamburger-menu');
    const nav = document.querySelector('.nav');
    const profileContainer = document.querySelector('.profile-container');
    const dropdownMenu = document.querySelector('.dropdown-menu');

    // Переключение бургер-меню
    hamburgerMenu.addEventListener('click', function() {
        nav.classList.toggle('active');

    });

    document.addEventListener('click', function(event) {
        const isClickInsideNav = nav.contains(event.target);
        const isClickOnHamburger = hamburgerMenu.contains(event.target);

        if (!isClickInsideNav && !isClickOnHamburger && nav.classList.contains('active')) {
            nav.classList.remove('active');
        }
    });


    const sliderContainer = document.querySelector('.slider-container');
    const cards = document.querySelectorAll('.card-people');
    const leftArrow = document.querySelector('.slider-arrow.left');
    const rightArrow = document.querySelector('.slider-arrow.right');
    const cardsContainer = document.querySelector('.cards-peoples');

    let currentIndex = 0;
    const cardsPerPage = window.innerWidth <= 768 ? 1 : 3; // 1 карточка для мобильных, 3 для десктопа

    // Функция для обновления видимых карточек
    function updateSlider() {
        const cardsWidth = cardsContainer.offsetWidth;
        const cardWidth = cards[0].offsetWidth;
        const gap = parseFloat(getComputedStyle(cards[0]).marginRight); // Получаем отступ справа

        // Рассчитываем смещение для отображения нужного количества карточек
        const offset = currentIndex * (cardWidth + gap);

        // Применяем трансформацию к всему контейнеру, чтобы двигать карточки
        sliderContainer.style.transform = `translateX(-${offset}px)`;

        // Обновляем состояние стрелок
        leftArrow.style.display = currentIndex === 0 ? 'none' : 'flex';
        rightArrow.style.display = currentIndex >= cards.length - cardsPerPage ? 'none' : 'flex';
    }

    // Обработчик клика по стрелке "назад"
    leftArrow.addEventListener('click', () => {
        // Проверяем, есть ли что листать назад
        if (currentIndex > 0) {
            currentIndex--;
            updateSlider();
        }
    });

    // Обработчик клика по стрелке "вперед"
    rightArrow.addEventListener('click', () => {
        // Проверяем, есть ли что листать вперед
        // Здесь мы сравниваем currentIndex с общей длиной массива карт минус количество карт, которые мы видим на экране
        if (currentIndex < cards.length - cardsPerPage) {
            currentIndex++;
            updateSlider();
        }
    });

    // Обработчик изменения размера окна для адаптивности
    window.addEventListener('resize', () => {
        // Пересчитываем количество карточек на странице при изменении размера
        const newCardsPerPage = window.innerWidth <= 768 ? 1 : 3;

        // Если количество карточек на странице изменилось, корректируем currentIndex
        if (newCardsPerPage !== (cardsPerPage)) {
            // Если перешли с десктопа на мобильный, то currentIndex должен быть 0 (первая карточка)
            if (newCardsPerPage === 1) {
                currentIndex = 0;
            } else {
                // Если перешли с мобильного на десктоп, нужно вычислить новую позицию
                // Это может быть немного сложнее, но для простоты приравняем к 0
                currentIndex = 0; // Можно усложнить, если нужно сохранить позицию
            }
            updateSlider();
        }
    });

    // Первоначальное обновление слайдера при загрузке страницы
    updateSlider();

});
