document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const searchForm           = document.getElementById('search-form');
    const searchInput          = document.getElementById('search-input');
    const loadingState         = document.getElementById('loading-state');
    const loadingText          = document.getElementById('loading-text');
    const errorState           = document.getElementById('error-state');
    const resultsContainer     = document.getElementById('results-container');
    const resultsGrid          = document.getElementById('results-grid');
    const resultsCount         = document.getElementById('results-count');
    const cardTemplate         = document.getElementById('result-card-template');
    const skeletonTemplate     = document.getElementById('skeleton-card-template');

    // History and Basket DOM elements
    const historyContainer     = document.getElementById('search-history-container');
    const historyItemsWrapper  = document.getElementById('search-history-items');
    const clearHistoryBtn      = document.getElementById('clear-history-btn');

    const basketToggle         = document.getElementById('basket-toggle');
    const basketDrawer         = document.getElementById('basket-drawer');
    const basketCloseBtn       = document.getElementById('basket-close-btn');
    const basketCount          = document.getElementById('basket-count');
    const basketItemsList      = document.getElementById('basket-items-list');
    const basketDashboard      = document.getElementById('basket-comparison-dashboard');
    const clearBasketBtn       = document.getElementById('clear-basket-btn');
    
    const basketTotalNahdi     = document.getElementById('basket-total-nahdi');
    const basketTotalDawaa     = document.getElementById('basket-total-dawaa');
    const basketTotalUnited    = document.getElementById('basket-total-united');
    const basketWinnerBanner   = document.getElementById('basket-winner-banner');

    // Product Modal DOM elements
    const productModal         = document.getElementById('product-modal');
    const modalCloseBtn        = document.getElementById('modal-close-btn');
    const modalProductImg      = document.getElementById('modal-product-img');
    const modalStoreBadge      = document.getElementById('modal-store-badge');
    const modalOfferBadge      = document.getElementById('modal-offer-badge');
    const modalProductTitle    = document.getElementById('modal-product-title');
    const modalPriceValue      = document.getElementById('modal-price-value');
    const modalEquivalentsList = document.getElementById('modal-equivalents-list');

    // Checkout Modal DOM elements
    const checkoutModal        = document.getElementById('checkout-modal');
    const checkoutCloseBtn     = document.getElementById('checkout-modal-close-btn');
    const checkoutStoreName    = document.getElementById('checkout-store-name');
    const checkoutItemsList    = document.getElementById('checkout-items-list');
    const checkoutOpenAllBtn   = document.getElementById('checkout-open-all-btn');

    // State Variables
    let allResults    = []; // Accumulate search results
    let basket        = JSON.parse(localStorage.getItem('tawfeery_basket')) || [];
    let favorites     = JSON.parse(localStorage.getItem('tawfeery_favorites')) || [];
    let searchHistory = JSON.parse(localStorage.getItem('tawfeery_history')) || [];
    let sessionScrapedProducts = JSON.parse(localStorage.getItem('tawfeery_scraped_cache')) || [];
    let customEquivalents = JSON.parse(localStorage.getItem('tawfeery_custom_equivalents')) || {};
    let currentQuery  = '';

    // Deals Section DOM
    const dealsSection  = document.getElementById('deals-section');
    const dealsGrid     = document.getElementById('deals-grid');
    const dealsLoading  = document.getElementById('deals-loading');
    const dealsCountBadge = document.getElementById('deals-count-badge');
    let dealsData       = [];
    let dealsShowCount  = 48;

    // Initialize UI
    renderHistory();
    updateBasketUI();
    fetchDeals();

    // ── BEST DEALS LOGIC ─────────────────────────────────────────────────────

    async function fetchDeals(retries = 3) {
        for (let attempt = 0; attempt < retries; attempt++) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 25000);
                const res = await fetch('/api/deals', { signal: controller.signal });
                clearTimeout(timeoutId);
                if (!res.ok) { dealsLoading.textContent = ''; return; }
                dealsData = await res.json();
                dealsLoading.style.display = 'none';
                if (!dealsData || dealsData.length === 0) return;
                renderDealsChunk();
                return;
            } catch (e) {
                if (attempt < retries - 1) {
                    dealsLoading.textContent = `جاري تحميل أفضل العروض... (محاولة ${attempt + 2})`;
                    await new Promise(r => setTimeout(r, 3000));
                } else {
                    dealsLoading.textContent = '';
                }
            }
        }
    }

    function renderDealsChunk() {
        const toShow = dealsData.slice(0, dealsShowCount);
        dealsGrid.innerHTML = '';
        toShow.forEach((item, idx) => {
            const card = buildDealCard(item, idx);
            dealsGrid.appendChild(card);
        });
        if (dealsCountBadge) dealsCountBadge.textContent = `${dealsData.length}+ منتج`;

        // Remove old load-more if exists
        const oldBtn = document.querySelector('.deals-load-more');
        if (oldBtn) oldBtn.remove();

        if (dealsShowCount < dealsData.length) {
            const btn = document.createElement('button');
            btn.className = 'deals-load-more';
            btn.textContent = `عرض المزيد (${dealsData.length - dealsShowCount}+)`;
            btn.addEventListener('click', () => {
                dealsShowCount += 48;
                renderDealsChunk();
            });
            dealsGrid.after(btn);
        }
    }

    function buildDealCard(item, idx) {
        const div = document.createElement('div');
        div.className = 'deal-card';
        div.style.animationDelay = `${idx * 0.06}s`;

        const hasOffer = !!item.offer;
        if (hasOffer) div.classList.add('has-offer');

        const img = item.image
            ? `<img src="${item.image}" alt="${item.name}" class="deal-img" onerror="this.style.display='none';this.parentElement.style.background='var(--bg-secondary)'">`
            : '<div class="deal-img-placeholder">💊</div>';

        const badgeClass = item.store.includes('Nahdi') ? 'store-nahdi'
            : item.store.includes('Dawaa') ? 'store-dawaa'
            : 'store-united';

        const offerHtml = item.offer
            ? `<div class="deal-offer-tag">🎁 ${item.offer}</div>`
            : '';

        const badgeLabel = hasOffer ? '🔥 عرض' : '💊 منتج';

        // Price processing — apply promo to effective price
        const regularPrice = parseFloat(item.price);
        const promoInfo = getPromoInfo(regularPrice, item.offer);
        let displayPrice = regularPrice;
        let strikePrice = null;

        if (promoInfo) {
            if (promoInfo.type === 'discount') {
                displayPrice = promoInfo.unitPrice;
                strikePrice = regularPrice;
            } else if (promoInfo.type === 'bundle') {
                displayPrice = promoInfo.unitPrice;
                strikePrice = regularPrice;
            } else if (promoInfo.type === 'delivery') {
                displayPrice = promoInfo.deliveryPrice;
                strikePrice = regularPrice;
            }
        }

        const strikeHtml = strikePrice && strikePrice < regularPrice
            ? `<span class="deal-price-strike">${regularPrice.toFixed(2)}</span>`
            : '';

        // Unit price display (based on effective price)
        let unitPriceHtml = '';
        if (item.quantity && item.quantity > 0) {
            const unitP = displayPrice / item.quantity;
            unitPriceHtml = `<div class="deal-unit-price">${unitP.toFixed(3)} SAR / الحبة</div>`;
        }

        // Promo label for deal cards
        let promoLabel = '';
        if (promoInfo && promoInfo.type === 'discount' && strikePrice) {
            const saving = regularPrice - displayPrice;
            promoLabel = `<div class="deal-promo-label">وفّر ${saving.toFixed(2)} SAR</div>`;
        } else if (promoInfo && promoInfo.type === 'bundle' && strikePrice) {
            promoLabel = `<div class="deal-promo-label">سعر الحبة بالعرض</div>`;
        } else if (promoInfo && promoInfo.type === 'delivery' && strikePrice) {
            promoLabel = `<div class="deal-promo-label">سعر التوصيل</div>`;
        }

        div.innerHTML = `
            <div class="deal-img-wrap">${img}</div>
            <div class="deal-body">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div class="deal-store-badge ${badgeClass}">${item.store}</div>
                    <span class="deal-type-badge ${hasOffer ? 'deal-type-offer' : 'deal-type-regular'}">${badgeLabel}</span>
                </div>
                <div class="deal-name">${item.name}</div>
                ${offerHtml}
                <div class="deal-price-row">
                    <div>
                        <span class="deal-price">${displayPrice.toFixed(2)} <span class="deal-currency">SAR</span></span>
                        ${strikeHtml}
                        ${promoLabel}
                        ${unitPriceHtml}
                    </div>
                    <a href="${item.link}" target="_blank" rel="noopener noreferrer" class="deal-buy-btn">عرض</a>
                </div>
            </div>
        `;
        return div;
    }

    // ── SEARCH LOGIC ─────────────────────────────────────────────────────────

    searchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = searchInput.value.trim();
        if (query) performSearch(query);
    });

    // Quick Search Pills Click
    document.querySelectorAll('.quick-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const query = pill.getAttribute('data-query');
            searchInput.value = query;
            performSearch(query);
        });
    });

    // Clear History Click
    clearHistoryBtn.addEventListener('click', () => {
        searchHistory = [];
        localStorage.setItem('tawfeery_history', JSON.stringify(searchHistory));
        renderHistory();
    });

    async function performSearch(query) {
        currentQuery = query;
        // Save to History
        if (!searchHistory.includes(query)) {
            searchHistory.unshift(query);
            if (searchHistory.length > 5) searchHistory.pop(); // Max 5 items
            localStorage.setItem('tawfeery_history', JSON.stringify(searchHistory));
            renderHistory();
        }

        // Reset UI State
        allResults = [];
        resultsGrid.innerHTML = '';
        resultsCount.textContent = '0';
        errorState.classList.add('hidden');
        dealsSection.style.display = 'none';
        resultsContainer.classList.remove('hidden');
        loadingState.classList.remove('hidden');
        if (loadingText) loadingText.textContent = 'جاري البحث في الصيدليات...';

        // Render Skeletons initially
        for (let i = 0; i < 6; i++) {
            const skeleton = skeletonTemplate.content.cloneNode(true);
            resultsGrid.appendChild(skeleton);
        }

        try {
            const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            let hasReceivedResults = false;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep incomplete last chunk

                for (const line of lines) {
                    const data = line.replace(/^data: /, '').trim();
                    if (!data) continue;

                    if (data === 'DONE') {
                        loadingState.classList.add('hidden');
                        
                        // Clear remaining skeletons if any
                        const skeletons = resultsGrid.querySelectorAll('.skeleton-card');
                        skeletons.forEach(s => s.remove());

                        // Cache search results in session cache
                        allResults.forEach(item => {
                            if (!sessionScrapedProducts.some(p => p.link === item.link)) {
                                sessionScrapedProducts.push(item);
                            }
                        });
                        localStorage.setItem('tawfeery_scraped_cache', JSON.stringify(sessionScrapedProducts));

                        if (allResults.length === 0) {
                            resultsContainer.classList.add('hidden');
                            dealsSection.style.display = '';
                            errorState.innerHTML = '<div class="error-icon">🔍</div><p>لم يتم العثور على نتائج. جرب كلمة بحث أخرى.</p>';
                            errorState.classList.remove('hidden');
                        } else {
                            resortGrid();
                        }
                        updateBasketUI();
                        return;
                    }

                    const parsed = JSON.parse(data);
                    const newItems = parsed.results || [];
                    
                    if (loadingText) {
                        loadingText.textContent = `وصلت نتائج ${parsed.store} — جاري انتظار الصيدليات المتبقية...`;
                    }

                    if (newItems.length === 0) continue;

                    // Remove skeletons on first real data
                    if (!hasReceivedResults) {
                        resultsGrid.innerHTML = '';
                        hasReceivedResults = true;
                    }

                    // Store new items
                    allResults.push(...newItems);

                    // Add items to UI
                    newItems.forEach((item) => {
                        const card = buildCard(item);
                        resultsGrid.appendChild(card);
                    });

                    resultsCount.textContent = allResults.length;
                }
            }
        } catch (error) {
            console.error('Search error:', error);
            loadingState.classList.add('hidden');
            resultsGrid.innerHTML = '';
            resultsContainer.classList.add('hidden');
            dealsSection.style.display = '';
            errorState.innerHTML = `
                <div class="error-icon">⚠️</div>
                <p>عذراً، حدث خطأ أثناء الاتصال. يرجى المحاولة مرة أخرى.</p>
                <button onclick="document.getElementById('search-form').dispatchEvent(new Event('submit'))" style="margin-top:1rem; padding:0.6rem 1.5rem; background:linear-gradient(135deg,#10b981,#059669); color:white; border:none; border-radius:20px; cursor:pointer; font-size:0.95rem; font-family:inherit;">إعادة المحاولة 🔄</button>
            `;
            errorState.classList.remove('hidden');
        }
    }

    function renderHistory() {
        if (searchHistory.length === 0) {
            historyContainer.classList.add('hidden');
            return;
        }
        historyContainer.classList.remove('hidden');
        historyItemsWrapper.innerHTML = '';
        searchHistory.forEach((query) => {
            const pill = document.createElement('button');
            pill.className = 'history-pill';
            pill.innerHTML = `
                <span>${query}</span>
                <span class="delete-history-item" data-query="${query}">&times;</span>
            `;
            
            // Search on click
            pill.addEventListener('click', (e) => {
                if (e.target.classList.contains('delete-history-item')) return;
                searchInput.value = query;
                performSearch(query);
            });

            // Delete single history item
            pill.querySelector('.delete-history-item').addEventListener('click', (e) => {
                e.stopPropagation();
                searchHistory = searchHistory.filter(q => q !== query);
                localStorage.setItem('tawfeery_history', JSON.stringify(searchHistory));
                renderHistory();
            });

            historyItemsWrapper.appendChild(pill);
        });
    }

    function buildCard(item, delayIndex = 0) {
        const clone = cardTemplate.content.cloneNode(true);
        const card  = clone.querySelector('.result-card');

        // Animations and Styles
        card.style.animationDelay = `${(delayIndex % 8) * 0.05}s`;
        card.classList.add('card-enter');

        // Image
        const img = clone.querySelector('.product-image');
        img.src = item.image || '';
        img.alt = item.name;
        img.onerror = () => {
            img.style.display = 'none';
            img.parentElement.style.background = 'var(--bg-secondary)';
        };

        // Text & Links
        clone.querySelector('.product-name').textContent = item.name;
        
        // ── Price Processing ──
        const regularPrice = parseFloat(item.price);
        const promoInfo = getPromoInfo(regularPrice, item.offer);
        const priceValEl = clone.querySelector('.price-value');
        const strikeValEl = clone.querySelector('.price-value-strikethrough');
        const promoTagEl = clone.querySelector('.promo-price-tag');
        
        if (promoInfo && promoInfo.type === 'discount' && promoInfo.unitPrice < regularPrice) {
            const saving = regularPrice - promoInfo.unitPrice;
            priceValEl.textContent = promoInfo.unitPrice.toFixed(2);
            strikeValEl.textContent = regularPrice.toFixed(2);
            strikeValEl.classList.remove('hidden');
            promoTagEl.innerHTML = `🏷️ خصم ${Math.round(promoInfo.pct * 100)}% (وفّر ${saving.toFixed(2)} SAR)`;
            promoTagEl.classList.remove('hidden');
            promoTagEl.style.color = '#34d399';
            promoTagEl.style.borderColor = 'rgba(52,211,153,0.3)';
            promoTagEl.style.background = 'rgba(16,185,129,0.1)';
        } else if (promoInfo && promoInfo.type === 'bundle' && promoInfo.unitPrice < regularPrice) {
            // Bundle deal: show effective unit price as main price with strikethrough
            priceValEl.textContent = promoInfo.unitPrice.toFixed(2);
            strikeValEl.textContent = regularPrice.toFixed(2);
            strikeValEl.classList.remove('hidden');
            // If this is a percentage-off-second deal, show the pct in the label
            const pctLabel = promoInfo.pct !== undefined
                ? `🏷️ خصم ${Math.round(promoInfo.pct * 100)}% على الحبة الثانية — سعر الحبة بالعرض: ${promoInfo.unitPrice.toFixed(2)} SAR`
                : `🏷️ سعر الحبة بالعرض: ${promoInfo.unitPrice.toFixed(2)} SAR`;
            promoTagEl.textContent = pctLabel;
            promoTagEl.classList.remove('hidden');
            promoTagEl.style.color = '';
            promoTagEl.style.borderColor = '';
            promoTagEl.style.background = '';
        } else if (promoInfo && promoInfo.type === 'delivery' && promoInfo.deliveryPrice < regularPrice) {
            // Delivery discount: show delivery price as main price with strikethrough
            priceValEl.textContent = promoInfo.deliveryPrice.toFixed(2);
            strikeValEl.textContent = regularPrice.toFixed(2);
            strikeValEl.classList.remove('hidden');
            const saving = regularPrice - promoInfo.deliveryPrice;
            promoTagEl.innerHTML = `🚚 سعر التوصيل بالعرض: ${promoInfo.deliveryPrice.toFixed(2)} SAR (وفّر ${saving.toFixed(2)} SAR)`;
            promoTagEl.classList.remove('hidden');
            promoTagEl.style.color = '#38bdf8';
            promoTagEl.style.borderColor = 'rgba(56,189,248,0.3)';
            promoTagEl.style.background = 'rgba(14,165,233,0.1)';
        } else {
            priceValEl.textContent = regularPrice.toFixed(2);
            strikeValEl.classList.add('hidden');
            promoTagEl.classList.add('hidden');
        }
        
        const buyBtn = clone.querySelector('.buy-btn');
        buyBtn.href = item.link;
        buyBtn.addEventListener('click', (e) => e.stopPropagation()); // prevent modal trigger

        // Store styling
        const badge = clone.querySelector('.store-badge');
        badge.textContent = item.store;
        if (item.store.includes('Nahdi'))        badge.classList.add('store-nahdi');
        else if (item.store.includes('Dawaa'))   badge.classList.add('store-dawaa');
        else if (item.store.includes('United'))  badge.classList.add('store-united');

        // Offer
        const offerBadge = clone.querySelector('.offer-badge');
        if (item.offer) {
            offerBadge.textContent = `🎁 ${item.offer}`;
            offerBadge.classList.remove('hidden');
        } else {
            offerBadge.classList.add('hidden');
        }

        // Favorites Button State
        const favBtn = clone.querySelector('.favorite-btn');
        const isFav = favorites.some(f => f.link === item.link);
        if (isFav) favBtn.classList.add('active');
        favBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleFavorite(item, favBtn);
        });

        // Basket Button State
        const bskBtn = clone.querySelector('.basket-btn');
        const inBsk = basket.some(b => b.link === item.link);
        if (inBsk) {
            bskBtn.style.background = 'rgba(16, 185, 129, 0.2)';
            bskBtn.style.borderColor = 'var(--primary-color)';
        }
        bskBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleBasket(item, bskBtn);
        });

        // Trigger Detailed Modal on Card click (excluding button clicks)
        card.addEventListener('click', () => openModal(item));

        return clone;
    }

    function resortGrid() {
        // Sort results by effective unit price (low to high)
        allResults.sort((a, b) => {
            const priceA = getEffectiveUnitPriceForSorting(parseFloat(a.price), a.offer);
            const priceB = getEffectiveUnitPriceForSorting(parseFloat(b.price), b.offer);
            return priceA - priceB;
        });
        
        resultsGrid.innerHTML = '';
        allResults.forEach((item, idx) => {
            const cardClone = buildCard(item, idx);
            if (idx === 0) {
                // Highlight the absolute cheapest item in results
                const badge = cardClone.querySelector('.best-price-badge');
                if (badge) badge.classList.remove('hidden');
                const card = cardClone.querySelector('.result-card');
                if (card) {
                    card.style.borderColor = 'rgba(16, 185, 129, 0.4)';
                    card.style.boxShadow = '0 0 25px rgba(16, 185, 129, 0.2)';
                }
            }
            resultsGrid.appendChild(cardClone);
        });
        resultsCount.textContent = allResults.length;
    }


    // ── FAVORITES LOGIC ──────────────────────────────────────────────────────

    function toggleFavorite(item, btnElement) {
        const index = favorites.findIndex(f => f.link === item.link);
        if (index === -1) {
            favorites.push(item);
            btnElement.classList.add('active');
        } else {
            favorites.splice(index, 1);
            btnElement.classList.remove('active');
        }
        localStorage.setItem('tawfeery_favorites', JSON.stringify(favorites));
    }


    // ── SMART BASKET COMPARISON LOGIC ────────────────────────────────────────

    basketToggle.addEventListener('click', () => basketDrawer.classList.toggle('open'));
    basketCloseBtn.addEventListener('click', () => basketDrawer.classList.remove('open'));
    clearBasketBtn.addEventListener('click', () => {
        basket = [];
        customEquivalents = {};
        localStorage.setItem('tawfeery_basket', JSON.stringify(basket));
        localStorage.setItem('tawfeery_custom_equivalents', JSON.stringify(customEquivalents));
        updateBasketUI();
        // Reset card basket states on the grid
        document.querySelectorAll('.basket-btn').forEach(btn => {
            btn.style.background = '';
            btn.style.borderColor = '';
        });
    });

    function toggleBasket(item, btnElement) {
        const index = basket.findIndex(b => b.link === item.link);
        if (index === -1) {
            // Add with default quantity of 1
            const basketItem = { ...item, quantity: 1 };
            basket.push(basketItem);
            if (btnElement) {
                btnElement.style.background = 'rgba(16, 185, 129, 0.2)';
                btnElement.style.borderColor = 'var(--primary-color)';
            }
        } else {
            basket.splice(index, 1);
            if (btnElement) {
                btnElement.style.background = '';
                btnElement.style.borderColor = '';
            }
        }
        localStorage.setItem('tawfeery_basket', JSON.stringify(basket));
        updateBasketUI();
    }

    function updateBasketUI() {
        basketCount.textContent = basket.reduce((acc, b) => acc + (b.quantity || 1), 0);

        if (basket.length === 0) {
            basketItemsList.innerHTML = `
                <div class="empty-basket-state">
                    <div class="basket-icon-large">🛒</div>
                    <p>سلتك فارغة حالياً. أضف منتجات من نتائج البحث لمقارنة الأسعار الإجمالية بين الصيدليات.</p>
                </div>
            `;
            basketDashboard.classList.add('hidden');
            return;
        }

        basketDashboard.classList.remove('hidden');
        basketItemsList.innerHTML = '';

        basket.forEach((item) => {
            const div = document.createElement('div');
            div.className = 'basket-item';
            
            const regularPrice = parseFloat(item.price);
            const promoPrice = getEffectiveUnitPrice(regularPrice, item.offer);
            const displayUnitPrice = (promoPrice !== null && promoPrice < regularPrice) ? promoPrice : regularPrice;
            const q = item.quantity || 1;

            const storesToCompare = [
                { name: 'صيدلية النهدي', key: 'Nahdi Online', class: 'nahdi', short: 'النهدي' },
                { name: 'صيدلية الدواء', key: 'Al-Dawaa', class: 'dawaa', short: 'الدواء' },
                { name: 'المتحدة', key: 'United Pharmacy', class: 'united', short: 'المتحدة' }
            ];

            let equivalentsHTML = '';
            storesToCompare.forEach(store => {
                if (item.store.includes(store.class === 'nahdi' ? 'Nahdi' : store.class === 'dawaa' ? 'Dawaa' : 'United')) {
                    return; // Skip native store
                }

                // Check if custom bound equivalent exists
                const customLink = customEquivalents[item.link]?.[store.key];
                let equiv = null;
                if (customLink) {
                    equiv = sessionScrapedProducts.find(p => p.link === customLink);
                }

                // If not custom bound, check auto-matching in cache
                if (!equiv) {
                    const storeCache = sessionScrapedProducts.filter(r => r.store.includes(store.key.split(' ')[0]));
                    equiv = findEquivalent(item, storeCache);
                }

                if (equiv) {
                    const isCustom = !!customLink;
                    const equivPromo = getPromoInfo(parseFloat(equiv.price), equiv.offer);
                    const equivEffectiveUnit = (equivPromo && equivPromo.type === 'bundle' && equivPromo.unitPrice < parseFloat(equiv.price))
                        ? equivPromo.unitPrice
                        : (equivPromo && equivPromo.type === 'delivery' ? equivPromo.deliveryPrice : parseFloat(equiv.price));
                    const equivOfferBadge = (equivPromo && equivEffectiveUnit < parseFloat(equiv.price))
                        ? `<span style="font-size:0.65rem; color:#10b981; margin-right:0.2rem;" title="${equiv.offer || ''}">🏷️ ${equivEffectiveUnit.toFixed(2)} SAR/حبة</span>`
                        : '';
                    equivalentsHTML += `
                        <div class="basket-custom-equiv-row">
                            <span class="store-dot ${store.class}"></span>
                            <span style="font-size: 0.72rem; color: var(--text-muted);">${store.short}:</span>
                            <span class="bound-equiv-name" title="${equiv.name}">${equiv.name} (${equiv.price.toFixed(2)} SAR${equivOfferBadge ? '' : ''})</span>
                            ${equivOfferBadge}
                            ${isCustom ? `<button class="unbind-equiv-btn" data-basket-link="${item.link}" data-store="${store.key}" title="إلغاء الربط المخصص">&times;</button>` : ''}
                        </div>
                    `;
                } else {
                    // Search session cache for same-brand suggestions
                    const storeCache = sessionScrapedProducts.filter(r => r.store.includes(store.key.split(' ')[0]));
                    const itemTokens = getTokens(item.name);
                    const brand = itemTokens[0];
                    
                    const candidates = storeCache.filter(cand => {
                        const candTokens = getTokens(cand.name);
                        return candTokens.includes(brand);
                    }).slice(0, 2);

                    if (candidates.length > 0) {
                        const pillsHTML = candidates.map(c => `
                            <button class="suggest-pill-btn" data-basket-link="${item.link}" data-store="${store.key}" data-equiv-link="${c.link}" title="${c.name}">
                                ${c.name.substring(0, 15)}... (${c.price.toFixed(2)} SAR)
                            </button>
                        `).join('');
                        
                        equivalentsHTML += `
                            <div class="basket-missing-equiv-row">
                                <span class="store-dot ${store.class}"></span>
                                <span style="font-size: 0.72rem; color: #ef4444; margin-left: 0.2rem;">${store.short} (نقص):</span>
                                <div class="suggest-pills-container">
                                    ${pillsHTML}
                                </div>
                            </div>
                        `;
                    } else {
                        equivalentsHTML += `
                            <div class="basket-missing-equiv-row">
                                <span class="store-dot ${store.class}"></span>
                                <span style="font-size: 0.72rem; color: #ef4444;">${store.short}: غير متوفر بديل</span>
                            </div>
                        `;
                    }
                }
            });

            div.innerHTML = `
                <div style="display: flex; gap: 0.8rem; align-items: center; width: 100%;">
                    <img src="${item.image || 'https://via.placeholder.com/150'}" alt="${item.name}" class="basket-item-img" onerror="this.src='https://via.placeholder.com/150'">
                    <div class="basket-item-info">
                        <div class="basket-item-name">${item.name}</div>
                        <div class="basket-item-store">${item.store}</div>
                        <div class="basket-item-qty-controls">
                            <button class="qty-btn qty-minus">-</button>
                            <span class="qty-val">${q}</span>
                            <button class="qty-btn qty-plus">+</button>
                        </div>
                    </div>
                    <div style="text-align: right; display: flex; flex-direction: column; justify-content: center; align-items: flex-end; gap: 0.2rem; min-width: 80px; margin-right: auto;">
                        <div class="basket-item-price-tag" style="font-size: 1rem;">${(displayUnitPrice * q).toFixed(2)} SAR</div>
                        <div style="font-size: 0.72rem; color: var(--text-muted);">${displayUnitPrice.toFixed(2)} / الحبة</div>
                    </div>
                    <button class="remove-basket-item" title="حذف" style="margin-right: 0.4rem;">&times;</button>
                </div>
                ${equivalentsHTML ? `<div class="basket-item-missing-section">${equivalentsHTML}</div>` : ''}
            `;
            div.style.flexDirection = 'column';
            div.style.alignItems = 'flex-start';

            // Quantity adjust event listeners
            div.querySelector('.qty-plus').addEventListener('click', () => {
                item.quantity = q + 1;
                localStorage.setItem('tawfeery_basket', JSON.stringify(basket));
                updateBasketUI();
            });

            div.querySelector('.qty-minus').addEventListener('click', () => {
                if (q > 1) {
                    item.quantity = q - 1;
                    localStorage.setItem('tawfeery_basket', JSON.stringify(basket));
                    updateBasketUI();
                }
            });

            div.querySelector('.remove-basket-item').addEventListener('click', () => {
                toggleBasket(item, null);
                // Synchronize search grid button highlights if visible
                const cards = resultsGrid.querySelectorAll('.result-card');
                cards.forEach(card => {
                    const buyBtn = card.querySelector('.buy-btn');
                    if (buyBtn && buyBtn.href === item.link) {
                        const bskBtn = card.querySelector('.basket-btn');
                        if (bskBtn) {
                            bskBtn.style.background = '';
                            bskBtn.style.borderColor = '';
                        }
                    }
                });
            });

            // Equivalent pills binding listeners
            div.querySelectorAll('.suggest-pill-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const bLink = btn.getAttribute('data-basket-link');
                    const storeKey = btn.getAttribute('data-store');
                    const equivLink = btn.getAttribute('data-equiv-link');
                    
                    if (!customEquivalents[bLink]) {
                        customEquivalents[bLink] = {};
                    }
                    customEquivalents[bLink][storeKey] = equivLink;
                    localStorage.setItem('tawfeery_custom_equivalents', JSON.stringify(customEquivalents));
                    updateBasketUI();
                });
            });

            // Unbind listeners
            div.querySelectorAll('.unbind-equiv-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const bLink = btn.getAttribute('data-basket-link');
                    const storeKey = btn.getAttribute('data-store');
                    
                    if (customEquivalents[bLink] && customEquivalents[bLink][storeKey]) {
                        delete customEquivalents[bLink][storeKey];
                        if (Object.keys(customEquivalents[bLink]).length === 0) {
                            delete customEquivalents[bLink];
                        }
                    }
                    localStorage.setItem('tawfeery_custom_equivalents', JSON.stringify(customEquivalents));
                    updateBasketUI();
                });
            });

            basketItemsList.appendChild(div);
        });

        calculateTotals();
    }

    function calculateTotals() {
        // Group all scraped cache results by store
        const storeResults = {
            'Nahdi Online':    sessionScrapedProducts.filter(r => r.store.includes('Nahdi')),
            'Al-Dawaa':        sessionScrapedProducts.filter(r => r.store.includes('Dawaa')),
            'United Pharmacy': sessionScrapedProducts.filter(r => r.store.includes('United'))
        };

        let nahdiTotal  = 0;
        let dawaaTotal  = 0;
        let unitedTotal = 0;

        let missingNahdi  = 0;
        let missingDawaa  = 0;
        let missingUnited = 0;

        basket.forEach((basketItem) => {
            const q = basketItem.quantity || 1;

            // ── Nahdi Online Equivalent
            if (basketItem.store.includes('Nahdi')) {
                nahdiTotal += calculateDiscountedPrice(basketItem.price, basketItem.offer, q);
            } else {
                let equiv = null;
                const customLink = customEquivalents[basketItem.link]?.[ 'Nahdi Online' ];
                if (customLink) {
                    equiv = sessionScrapedProducts.find(p => p.link === customLink);
                }
                if (!equiv) {
                    equiv = findEquivalent(basketItem, storeResults['Nahdi Online']);
                }
                
                if (equiv) {
                    nahdiTotal += calculateDiscountedPrice(equiv.price, equiv.offer, q);
                } else {
                    missingNahdi += q;
                }
            }

            // ── Al-Dawaa Equivalent
            if (basketItem.store.includes('Dawaa')) {
                dawaaTotal += calculateDiscountedPrice(basketItem.price, basketItem.offer, q);
            } else {
                let equiv = null;
                const customLink = customEquivalents[basketItem.link]?.[ 'Al-Dawaa' ];
                if (customLink) {
                    equiv = sessionScrapedProducts.find(p => p.link === customLink);
                }
                if (!equiv) {
                    equiv = findEquivalent(basketItem, storeResults['Al-Dawaa']);
                }
                
                if (equiv) {
                    dawaaTotal += calculateDiscountedPrice(equiv.price, equiv.offer, q);
                } else {
                    missingDawaa += q;
                }
            }

            // ── United Pharmacy Equivalent
            if (basketItem.store.includes('United')) {
                unitedTotal += calculateDiscountedPrice(basketItem.price, basketItem.offer, q);
            } else {
                let equiv = null;
                const customLink = customEquivalents[basketItem.link]?.[ 'United Pharmacy' ];
                if (customLink) {
                    equiv = sessionScrapedProducts.find(p => p.link === customLink);
                }
                if (!equiv) {
                    equiv = findEquivalent(basketItem, storeResults['United Pharmacy']);
                }
                
                if (equiv) {
                    unitedTotal += calculateDiscountedPrice(equiv.price, equiv.offer, q);
                } else {
                    missingUnited += q;
                }
            }
        });

        const totalItemsInBasket = basket.reduce((acc, b) => acc + (b.quantity || 1), 0);

        // Render Nahdi total
        if (missingNahdi > 0) {
            basketTotalNahdi.innerHTML = `${nahdiTotal.toFixed(2)} SAR <span style="font-size:0.75rem; color:#f87171;">(نقص ${missingNahdi})</span>`;
        } else {
            basketTotalNahdi.innerHTML = `${nahdiTotal.toFixed(2)} SAR`;
        }

        // Render Dawaa total
        if (missingDawaa > 0) {
            basketTotalDawaa.innerHTML = `${dawaaTotal.toFixed(2)} SAR <span style="font-size:0.75rem; color:#f87171;">(نقص ${missingDawaa})</span>`;
        } else {
            basketTotalDawaa.innerHTML = `${dawaaTotal.toFixed(2)} SAR`;
        }

        // Render United total
        if (missingUnited > 0) {
            basketTotalUnited.innerHTML = `${unitedTotal.toFixed(2)} SAR <span style="font-size:0.75rem; color:#f87171;">(نقص ${missingUnited})</span>`;
        } else {
            basketTotalUnited.innerHTML = `${unitedTotal.toFixed(2)} SAR`;
        }

        // Determine Winner
        const scoreNahdi  = { total: nahdiTotal,  missing: missingNahdi,  name: 'صيدلية النهدي' };
        const scoreDawaa  = { total: dawaaTotal,  missing: missingDawaa,  name: 'صيدلية الدواء' };
        const scoreUnited = { total: unitedTotal, missing: missingUnited, name: 'المتحدة' };

        const candidates = [scoreNahdi, scoreDawaa, scoreUnited];
        // Sort primarily by fewest missing items, then by lowest total cost
        candidates.sort((a, b) => {
            if (a.missing !== b.missing) return a.missing - b.missing;
            return a.total - b.total;
        });

        const winner = candidates[0];

        // Clear previous winner formatting
        basketTotalNahdi.classList.remove('winner');
        basketTotalDawaa.classList.remove('winner');
        basketTotalUnited.classList.remove('winner');

        if (winner.missing === totalItemsInBasket) {
            basketWinnerBanner.innerHTML = '🔍 ابحث عن أدوية لمطابقة الأسعار الإجمالية';
        } else {
            if (winner.name === 'صيدلية النهدي')  basketTotalNahdi.classList.add('winner');
            if (winner.name === 'صيدلية الدواء')  basketTotalDawaa.classList.add('winner');
            if (winner.name === 'المتحدة')        basketTotalUnited.classList.add('winner');

            let bannerHTML = `🎉 <strong>${winner.name}</strong> هي الأوفر لك بإجمالي <strong>${winner.total.toFixed(2)} ريال</strong>`;
            if (winner.missing > 0) {
                bannerHTML += ` <span style="font-size:0.75rem; opacity:0.8;">(مع نقص ${winner.missing} حبة غير متوفرة)</span>`;
            }
            basketWinnerBanner.innerHTML = bannerHTML;
        }
    }


    // ── PRICE ANALYSIS ENGINE ───────────────────────────────────────────────

    /**
     * Returns structured promo info:
     * - type 'bundle': multi-buy deal, unitPrice = effective per-unit price
     * - type 'delivery': Al-Dawaa delivery discount, deliveryPrice = discounted price
     * - null: no recognized discount
     */
    function getPromoInfo(price, offer) {
        if (!offer) return null;
        const o = offer.toLowerCase();

        // Al-Dawaa delivery price pattern: "سعر التوصيل: X.XX ريال (وفّر Y.YY ريال)"
        let m = o.match(/سعر\s*التوصيل[:\s]*(\d+\.?\d*)/);
        if (m) {
            return { type: 'delivery', deliveryPrice: parseFloat(m[1]) };
        }

        // Bundle: "اشتري 2 بقيمة 1" → Buy 2 for price of 1 (1+1 free)
        if (o.includes('بقيمة 1') || (o.includes('2 بقيمة') && o.includes('1'))) {
            return { type: 'bundle', unitPrice: price / 2 };
        }

        // Bundle: Buy 2 For X / اشتري 2 بسعر X
        m = o.match(/(?:buy\s+2\s+for|اشتري\s+2\s+بسعر)\s*(\d+\.?\d*)/);
        if (m) return { type: 'bundle', unitPrice: parseFloat(m[1]) / 2 };

        // Bundle: Buy 2nd for X → effective unit = (price + X) / 2
        // Make the Kashida (ـ) optional using بـ?
        m = o.match(/(?:الحبة\s+الثانية\s+بـ?|buy\s+2nd\s+for|اشتري\s+الحبة\s+الثانية\s+بـ?)\s*(\d+\.?\d*)/);
        if (m) return { type: 'bundle', unitPrice: (price + parseFloat(m[1])) / 2 };

        // Bundle: 1+1 free (or اشتري 2 بقيمة 1)
        if (o.includes('1 + 1') || o.includes('1+1') || o.includes('بقيمة 1') || (o.includes('مجانا') && o.includes('1') && !o.includes('2')) || o.includes('حبة + حبة مجانا') || o.includes('حبة + حبة مجاناً')) {
            return { type: 'bundle', unitPrice: price / 2 };
        }

        // Bundle: 2+1 free
        if (o.includes('2 + 1') || o.includes('2+1') || (o.includes('مجانا') && o.includes('2')) || o.includes('حبتين + حبة مجانا') || o.includes('حبتين + حبة مجاناً')) {
            return { type: 'bundle', unitPrice: (price * 2) / 3 };
        }

        // Simple discount: "خصم X%" or "وفر X%" (straight percentage off)
        m = o.match(/(?:خصم|وفر|save)\s*(\d+)\s*%/ui);
        if (m) {
            const discountPct = parseFloat(m[1]) / 100;
            const discountedPrice = price * (1 - discountPct);
            return { type: 'discount', pct: discountPct, unitPrice: discountedPrice };
        }

        // Generic: X% off second item – e.g. "خصم 30% على الحبة الثانية", "50% off second"
        m = o.match(/(?:خصم\s*)?(\d+)\s*%(?:\s*(?:على|off)?\s*(?:الحبه?\s*)?(?:الثانيه?|second))/u);
        if (!m) {
            m = o.match(/(\d+)\s*%/);
            if (m && !(o.includes('الثانيه') || o.includes('الثانية') || o.includes('second'))) {
                m = null;
            }
        }
        if (m) {
            const discountPct = parseFloat(m[1]) / 100;
            const unitPrice = (price + price * (1 - discountPct)) / 2;
            return { type: 'bundle', pct: discountPct, unitPrice };
        }

        return null;
    }

    // For sorting: bundle and delivery deals affect the comparison price
    function getEffectiveUnitPriceForSorting(price, offer) {
        const info = getPromoInfo(price, offer);
        if (info) {
            if (info.type === 'bundle') return info.unitPrice;
            if (info.type === 'delivery') return info.deliveryPrice;
        }
        return price;
    }

    // Returns effective unit price for bundle or delivery deals
    function getEffectiveUnitPrice(price, offer) {
        const info = getPromoInfo(price, offer);
        if (info) {
            if (info.type === 'bundle') return info.unitPrice;
            if (info.type === 'delivery') return info.deliveryPrice;
        }
        return null;
    }

    function calculateDiscountedPrice(price, offer, quantity) {
        if (!offer || quantity <= 0) return price * quantity;
        const info = getPromoInfo(price, offer);
        if (!info) return price * quantity;

        if (info.type === 'bundle') {
            const o = offer.toLowerCase();

            // Buy 2 for price of 1 (اشتري 2 بقيمة 1 = 1+1 free)
            if (o.includes('بقيمة 1') || (o.includes('2 بقيمة') && o.includes('1'))) {
                const pairs = Math.floor(quantity / 2);
                const singles = quantity % 2;
                return (pairs + singles) * price;
            }

            // Buy 2 For X
            let m = o.match(/(?:buy\s+2\s+for|اشتري\s+2\s+بسعر|اشتري\s+2\s+بقيمة)\s*(\d+\.?\d*)/);
            if (m) {
                const promoPrice = parseFloat(m[1]);
                const pairs = Math.floor(quantity / 2);
                const singles = quantity % 2;
                return (pairs * promoPrice) + (singles * price);
            }

            // Buy 2nd for X
            // Make the Kashida (ـ) optional using بـ?
            m = o.match(/(?:الحبة\s+الثانية\s+بـ?|buy\s+2nd\s+for|اشتري\s+الحبة\s+الثانية\s+بـ?)\s*(\d+\.?\d*)/);
            if (m) {
                const secondPrice = parseFloat(m[1]);
                const pairs = Math.floor(quantity / 2);
                const singles = quantity % 2;
                return pairs * (price + secondPrice) + (singles * price);
            }

            // 1+1 free (or "اشتري 2 بقيمة 1")
            if (o.includes('1 + 1') || o.includes('1+1') || o.includes('بقيمة 1') || (o.includes('مجانا') && o.includes('1') && !o.includes('2')) || o.includes('حبة + حبة مجانا') || o.includes('حبة + حبة مجاناً')) {
                const pairs = Math.floor(quantity / 2);
                const singles = quantity % 2;
                return (pairs + singles) * price;
            }

            // 2+1 free
            if (o.includes('2 + 1') || o.includes('2+1') || (o.includes('مجانا') && o.includes('2')) || o.includes('حبتين + حبة مجانا') || o.includes('حبتين + حبة مجاناً')) {
                const triplets = Math.floor(quantity / 3);
                const remainder = quantity % 3;
                return (triplets * 2 + remainder) * price;
            }

            // Generic X% off second item – use pct stored in promoInfo if available
            if (info.pct !== undefined) {
                const discountPct = info.pct;
                const pairs = Math.floor(quantity / 2);
                const singles = quantity % 2;
                // each pair: full price + second at (1-pct) price
                return pairs * (price + price * (1 - discountPct)) + (singles * price);
            }

            // Legacy fallback: 50% off second (in case pct wasn't captured above)
            if (o.includes('50%') || o.includes('50 %')) {
                const pairs = Math.floor(quantity / 2);
                const singles = quantity % 2;
                return pairs * (price + price * 0.5) + (singles * price);
            }
        } else if (info.type === 'discount') {
            return info.unitPrice * quantity;
        } else if (info.type === 'delivery') {
            return info.deliveryPrice * quantity;
        }

        return price * quantity;
    }


    // ── FUZZY STRING MATCHING ENGINE ─────────────────────────────────────────

    function cleanName(name) {
        if (!name) return '';
        // Remove Arabic tatweer/kashida completely
        let cleaned = name.toLowerCase().replace(/ـ/g, '');
        // Normalize Arabic letters and remove minor characters/brackets/punctuation
        return cleaned
            .replace(/[أإآأ]/g, 'ا')
            .replace(/ة/g, 'ه')
            .replace(/ى/g, 'ي')
            .replace(/[،؛؟?–—:;!*&|"'\-_.,()\/\[\]+]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function getTokens(name) {
        const cleaned = cleanName(name);
        const stopWords = new Set([
            'علبه', 'قرص', 'كبسوله', 'مل', 'جم', 'حبة', 'حبة/', 'حبات', 'ملج', 'جرام',
            'tablets', 'capsules', 'tabs', 'cap', 'ml', 'mg', 'g', 'pack', 'pcs', 'tablet', 'capsule',
            'من', 'مع', 'في', 'ال', 'ar', 'en', 'او', 'أو', 'ام', 'أم', 'على', 'عن'
        ]);
        return cleaned.split(' ').map(t => {
            let token = t;
            // Strip Arabic definite article "ال" if length allows
            if (token.startsWith('ال') && token.length > 4) {
                token = token.substring(2);
            }
            // Strip Arabic prefix "لل" (for/to the) if length allows
            if (token.startsWith('لل') && token.length > 4) {
                token = token.substring(2);
            }
            return token;
        }).filter(t => t.length > 1 && !stopWords.has(t));
    }

    function findEquivalent(item, otherStoreResults) {
        let bestMatch = null;
        let highestScore = 0;

        const itemTokens = getTokens(item.name);
        if (itemTokens.length === 0) return null;
        const brand = itemTokens[0]; // Primary brand indicator

        for (const candidate of otherStoreResults) {
            const candidateTokens = getTokens(candidate.name);
            if (candidateTokens.length === 0) continue;

            // Brand protection: both names must contain the brand name
            if (candidateTokens[0] !== brand) {
                if (!candidateTokens.includes(brand) && !itemTokens.includes(candidateTokens[0])) {
                    continue;
                }
            }

            // Compute Token Intersection
            let intersection = 0;
            for (const t of itemTokens) {
                if (candidateTokens.includes(t)) {
                    intersection++;
                }
            }

            // Overlap Score relative to the shorter string tokens
            const minSize = Math.min(itemTokens.length, candidateTokens.length);
            const overlapScore = intersection / minSize;

            // Jaccard similarity index to resolve length mismatch ties
            const jaccard = intersection / (itemTokens.length + candidateTokens.length - intersection);
            const score = (overlapScore * 0.75) + (jaccard * 0.25);

            if (score > highestScore && score >= 0.5) {
                highestScore = score;
                bestMatch = candidate;
            }
        }

        // --- Fallback: Looser matching if no strong match found ---
        if (!bestMatch) {
            for (const candidate of otherStoreResults) {
                const candidateTokens = getTokens(candidate.name);
                if (candidateTokens.length === 0) continue;

                // Loose brand containment check
                if (candidateTokens.includes(brand) || itemTokens.includes(candidateTokens[0])) {
                    let intersection = 0;
                    for (const t of itemTokens) {
                        if (candidateTokens.includes(t)) intersection++;
                    }
                    if (intersection > 0) {
                        const minSize = Math.min(itemTokens.length, candidateTokens.length);
                        const overlapScore = intersection / minSize;
                        const jaccard = intersection / (itemTokens.length + candidateTokens.length - intersection);
                        const score = (overlapScore * 0.75) + (jaccard * 0.25);
                        
                        if (score > highestScore && score >= 0.3) {
                            highestScore = score;
                            bestMatch = candidate;
                        }
                    }
                }
            }
        }

        return bestMatch;
    }


    // ── PRODUCT DETAILS MODAL ────────────────────────────────────────────────

    function openModal(item) {
        modalProductImg.src = item.image || '';
        modalProductImg.onerror = () => {
            modalProductImg.src = 'https://via.placeholder.com/200?text=No+Image';
        };

        modalProductTitle.textContent = item.name;
        
        // Show price & promo info in modal
        const regularPrice = parseFloat(item.price);
        const promoInfo = getPromoInfo(regularPrice, item.offer);
        
        if (promoInfo && promoInfo.type === 'discount' && promoInfo.unitPrice < regularPrice) {
            const saving = regularPrice - promoInfo.unitPrice;
            modalPriceValue.innerHTML = `${promoInfo.unitPrice.toFixed(2)} SAR <span style="font-size: 0.95rem; text-decoration: line-through; color: var(--text-muted); font-weight: normal; margin-right: 0.5rem;">${regularPrice.toFixed(2)} SAR</span> <div style="font-size:0.75rem; color:#34d399; margin-top:0.25rem;">🏷️ خصم ${Math.round(promoInfo.pct * 100)}% (وفّر ${saving.toFixed(2)} SAR)</div>`;
        } else if (promoInfo && promoInfo.type === 'bundle' && promoInfo.unitPrice < regularPrice) {
            // Bundle deal: show effective per-unit price with strikethrough
            modalPriceValue.innerHTML = `${promoInfo.unitPrice.toFixed(2)} SAR <span style="font-size: 0.95rem; text-decoration: line-through; color: var(--text-muted); font-weight: normal; margin-right: 0.5rem;">${regularPrice.toFixed(2)} SAR</span> <div style="font-size:0.75rem; color:#34d399; margin-top:0.25rem;">(سعر الحبة بالعرض)</div>`;
        } else if (promoInfo && promoInfo.type === 'delivery' && promoInfo.deliveryPrice < regularPrice) {
            // Delivery discount: show delivery price as main price with strikethrough
            const saving = regularPrice - promoInfo.deliveryPrice;
            modalPriceValue.innerHTML = `${promoInfo.deliveryPrice.toFixed(2)} SAR <span style="font-size: 0.95rem; text-decoration: line-through; color: var(--text-muted); font-weight: normal; margin-right: 0.5rem;">${regularPrice.toFixed(2)} SAR</span> <div style="font-size:0.78rem; color:#38bdf8; margin-top:0.3rem;">🚚 سعر التوصيل بالعرض (وفّر ${saving.toFixed(2)} SAR)</div>`;
        } else {
            modalPriceValue.textContent = `${regularPrice.toFixed(2)} SAR`;
        }

        // Store badge
        modalStoreBadge.textContent = item.store;
        modalStoreBadge.className = 'store-badge';
        if (item.store.includes('Nahdi'))        modalStoreBadge.classList.add('store-nahdi');
        else if (item.store.includes('Dawaa'))   modalStoreBadge.classList.add('store-dawaa');
        else if (item.store.includes('United'))  modalStoreBadge.classList.add('store-united');

        // Offer
        if (item.offer) {
            modalOfferBadge.textContent = `🎁 ${item.offer}`;
            modalOfferBadge.classList.remove('hidden');
        } else {
            modalOfferBadge.classList.add('hidden');
        }

        // Equivalents Matching Section
        modalEquivalentsList.innerHTML = '';

        const storeConfigs = [
            { name: 'صيدلية النهدي', key: 'Nahdi Online', class: 'store-nahdi' },
            { name: 'صيدلية الدواء', key: 'Al-Dawaa', class: 'store-dawaa' },
            { name: 'المتحدة', key: 'United Pharmacy', class: 'store-united' }
        ];

        storeConfigs.forEach((config) => {
            // Skip the store of the current product
            if (item.store === config.key) return;

            const targets = allResults.filter(r => r.store === config.key);
            const equiv = findEquivalent(item, targets);

            const div = document.createElement('div');
            div.className = 'equivalent-row';

            if (equiv) {
                const eqRegPrice = parseFloat(equiv.price);
                const eqPromoInfo = getPromoInfo(eqRegPrice, equiv.offer);
                let displayPrice = eqRegPrice;
                let priceNote = '';

                if (eqPromoInfo && eqPromoInfo.type === 'bundle' && eqPromoInfo.unitPrice < eqRegPrice) {
                    displayPrice = eqPromoInfo.unitPrice;
                    priceNote = `<span style="font-size:0.7rem; color:#34d399;">(بالعرض)</span>`;
                } else if (eqPromoInfo && eqPromoInfo.type === 'delivery' && eqPromoInfo.deliveryPrice < eqRegPrice) {
                    priceNote = `<span style="font-size:0.7rem; color:#38bdf8;">🚚 ${eqPromoInfo.deliveryPrice.toFixed(2)} للتوصيل</span>`;
                }

                div.innerHTML = `
                    <span class="eq-store-name"><span class="store-badge ${config.class}">${config.name}</span></span>
                    <span class="eq-price">
                        ${displayPrice.toFixed(2)} SAR 
                        ${priceNote}
                    </span>
                    <a href="${equiv.link}" target="_blank" rel="noopener noreferrer" class="eq-link">عرض 🔗</a>
                `;
            } else {
                div.innerHTML = `
                    <span class="eq-store-name"><span class="store-badge ${config.class}">${config.name}</span></span>
                    <span class="eq-missing">غير متوفر في نتائج هذا البحث</span>
                `;
            }
            modalEquivalentsList.appendChild(div);
        });

        productModal.classList.add('open');
    }

    function closeModal() {
        productModal.classList.remove('open');
    }

    modalCloseBtn.addEventListener('click', closeModal);
    productModal.addEventListener('click', (e) => {
        if (e.target === productModal) closeModal();
    });

    // ── CHECKOUT MODAL LOGIC ────────────────────────────────────────────────
    function openCheckoutModal(storeName) {
        checkoutStoreName.textContent = storeName === 'Nahdi Online' ? 'صيدلية النهدي' : storeName === 'Al-Dawaa' ? 'صيدلية الدواء' : 'المتحدة';
        checkoutItemsList.innerHTML = '';
        
        const storeResults = sessionScrapedProducts.filter(r => r.store.includes(storeName.split(' ')[0]));
        const linksToOpen = [];

        basket.forEach(basketItem => {
            let equiv = null;
            const q = basketItem.quantity || 1;

            if (basketItem.store.includes(storeName.split(' ')[0])) {
                equiv = basketItem;
            } else {
                const customLink = customEquivalents[basketItem.link]?.[storeName];
                if (customLink) {
                    equiv = sessionScrapedProducts.find(p => p.link === customLink);
                }
                if (!equiv) {
                    equiv = findEquivalent(basketItem, storeResults);
                }
            }

            const row = document.createElement('div');
            row.className = 'checkout-item-row';

            if (equiv) {
                const regularPrice = parseFloat(equiv.price);
                const displayPrice = getEffectiveUnitPrice(regularPrice, equiv.offer) || regularPrice;
                const totalCost = displayPrice * q;
                
                row.innerHTML = `
                    <div class="checkout-item-info">
                        <div class="checkout-item-title" title="${equiv.name}">${equiv.name}</div>
                        <div class="checkout-item-price">${q} × ${displayPrice.toFixed(2)} SAR = ${totalCost.toFixed(2)} SAR</div>
                    </div>
                    <a href="${equiv.link}" target="_blank" rel="noopener noreferrer" class="checkout-item-link-btn">
                        شراء المنتج 🔗
                    </a>
                `;
                linksToOpen.push(equiv.link);
            } else {
                row.innerHTML = `
                    <div class="checkout-item-info">
                        <div class="checkout-item-title" style="color: var(--text-muted);" title="${basketItem.name}">${basketItem.name}</div>
                        <div class="checkout-item-price">${q} × نقص</div>
                    </div>
                    <span class="checkout-item-missing-badge">غير متوفر</span>
                `;
            }
            checkoutItemsList.appendChild(row);
        });

        // Set up "Open All" button
        checkoutOpenAllBtn.onclick = () => {
            if (linksToOpen.length === 0) return;
            let blocked = false;
            linksToOpen.forEach((link) => {
                const newTab = window.open(link, '_blank');
                if (!newTab) {
                    blocked = true;
                }
            });
            if (blocked) {
                alert('⚠️ تم حظر فتح بعض الروابط تلقائياً من قبل متصفحك. يرجى السماح بالنوافذ المنبثقة (Pop-ups) لهذا الموقع من شريط العنوان.');
            }
        };

        checkoutModal.classList.add('open');
    }

    function closeCheckoutModal() {
        checkoutModal.classList.remove('open');
    }

    checkoutCloseBtn.addEventListener('click', closeCheckoutModal);
    checkoutModal.addEventListener('click', (e) => {
        if (e.target === checkoutModal) closeCheckoutModal();
    });

    // Delegated click listener for checkout buttons in basket drawer
    basketDrawer.addEventListener('click', (e) => {
        const btn = e.target.closest('.checkout-store-btn');
        if (btn) {
            const storeName = btn.getAttribute('data-store');
            openCheckoutModal(storeName);
        }
    });
});
