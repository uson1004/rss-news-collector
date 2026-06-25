import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import { requestJson } from './utils/api';
import { createLatestRequestTracker } from './utils/latestRequest';
import { supabase, supabaseConfigured } from './utils/supabase';
import { normalizeArticleInput } from './utils/url';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const DEFAULT_SETTINGS = {
  fontSize: 18,
  lineHeight: 1.75,
  paragraphSpacing: 1.4,
  contentWidth: 720,
  theme: 'light',
};

const TRANSLATE_TARGETS = [
  { label: '한국어', value: 'Korean' },
  { label: '영어', value: 'English' },
  { label: '일본어', value: 'Japanese' },
  { label: '중국어(간체)', value: 'Simplified Chinese' },
];

const DEFAULT_RSS_CATEGORIES = [
  { id: 'idea_radar', label: '아이디어 레이더' },
  { id: 'geeknews', label: '긱뉴스' },
  { id: 'android', label: '안드로이드' },
  { id: 'tech', label: 'IT' },
  { id: 'business', label: '경제' },
  { id: 'world', label: '사회/세계' },
  { id: 'science', label: '과학' },
  { id: 'sports', label: '스포츠' },
];

const SAMPLE_URL = `${API_BASE}/demo/article`;
const SAMPLE_URLS = [
  { label: '데모 기사', url: SAMPLE_URL },
  {
    label: 'MDN 접근성 문서',
    url: 'https://developer.mozilla.org/ko/docs/Learn_web_development/Core/Accessibility/What_is_accessibility',
  },
  { label: 'FastAPI 문서', url: 'https://fastapi.tiangolo.com/ko/' },
  {
    label: 'Django 릴리스 글',
    url: 'https://www.djangoproject.com/weblog/2025/dec/03/django-60-released/',
  },
];

function readHashRoute() {
  const route = window.location.hash.replace('#', '') || '/news';
  return ['/news', '/url', '/reader'].includes(route) ? route : '/news';
}

function App() {
  const [url, setUrl] = useState('');
  const [article, setArticle] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [summary, setSummary] = useState(null);
  const [summaryStatus, setSummaryStatus] = useState('idle');
  const [summaryError, setSummaryError] = useState('');
  const [articleInsight, setArticleInsight] = useState(null);
  const [articleInsightStatus, setArticleInsightStatus] = useState('idle');
  const [articleInsightError, setArticleInsightError] = useState('');
  const [followUpPrompt, setFollowUpPrompt] = useState(null);
  const [followUpPromptStatus, setFollowUpPromptStatus] = useState('idle');
  const [followUpPromptError, setFollowUpPromptError] = useState('');
  const [copyStatus, setCopyStatus] = useState('idle');
  const [targetLanguage, setTargetLanguage] = useState(TRANSLATE_TARGETS[0].value);
  const [translation, setTranslation] = useState(null);
  const [translationStatus, setTranslationStatus] = useState('idle');
  const [translationError, setTranslationError] = useState('');
  const [activeCategory, setActiveCategory] = useState('geeknews');
  const [categories, setCategories] = useState(DEFAULT_RSS_CATEGORIES);
  const [categoriesStatus, setCategoriesStatus] = useState('idle');
  const [categoriesError, setCategoriesError] = useState('');
  const [feedItems, setFeedItems] = useState([]);
  const [feedStatus, setFeedStatus] = useState('idle');
  const [feedError, setFeedError] = useState('');
  const [todoItems, setTodoItems] = useState([]);
  const [todoStatus, setTodoStatus] = useState('idle');
  const [todoError, setTodoError] = useState('');
  const [newsletterModalOpen, setNewsletterModalOpen] = useState(false);
  const [newsletterModalStep, setNewsletterModalStep] = useState(1);
  const [newsletterDraft, setNewsletterDraft] = useState({
    label: '',
    searchHint: '',
    candidates: [],
    selectedFeedUrls: [],
  });
  const [newsletterDraftStatus, setNewsletterDraftStatus] = useState('idle');
  const [newsletterDraftError, setNewsletterDraftError] = useState('');
  const [newsletterEmail, setNewsletterEmail] = useState('');
  const [newsletterCategoryId, setNewsletterCategoryId] = useState('geeknews');
  const [newsletterSubscribeStatus, setNewsletterSubscribeStatus] = useState('idle');
  const [newsletterSubscribeError, setNewsletterSubscribeError] = useState('');
  const [newsletterSubscribeMessage, setNewsletterSubscribeMessage] = useState('');
  const [ttsStatus, setTtsStatus] = useState('idle');
  const [ttsError, setTtsError] = useState('');
  const [route, setRoute] = useState(() => readHashRoute());
  const ttsParagraphsRef = useRef([]);
  const ttsIndexRef = useRef(0);
  const feedRequestTrackerRef = useRef(null);
  if (!feedRequestTrackerRef.current) {
    feedRequestTrackerRef.current = createLatestRequestTracker();
  }
  const [settings, setSettings] = useState(() => {
    const saved = localStorage.getItem('reader-settings');
    try {
      return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : DEFAULT_SETTINGS;
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  useEffect(() => {
    localStorage.setItem('reader-settings', JSON.stringify(settings));
    document.documentElement.dataset.theme = settings.theme;
  }, [settings]);

  useEffect(() => {
    loadCategory('idea_radar');
  }, []);

  useEffect(() => {
    loadCategories();
  }, []);

  useEffect(() => {
    if (!supabaseConfigured) {
      setTodoStatus('unavailable');
      return undefined;
    }

    let active = true;

    async function loadTodoItems() {
      setTodoStatus('loading');
      setTodoError('');

      const { data, error } = await supabase.from('todos').select('id, name').order('id', { ascending: true });

      if (!active) {
        return;
      }

      if (error) {
        setTodoStatus('error');
        setTodoError(error.message);
        return;
      }

      setTodoItems(data ?? []);
      setTodoStatus('success');
    }

    loadTodoItems();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!window.location.hash) {
      window.history.replaceState(null, '', '#/news');
    }

    function handleHashChange() {
      setRoute(readHashRoute());
    }

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  useEffect(() => {
    if (route !== '/reader') {
      clearReaderState();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [route]);

  useEffect(() => {
    if (route !== '/reader') return;

    const targetUrl = sessionStorage.getItem('reader-target-url');
    if (!targetUrl) {
      setStatus('error');
      setError('읽을 URL이 없어요. 뉴스나 URL 입력 화면에서 글을 선택해 주세요.');
      return;
    }

    if (article?.url === targetUrl || status === 'loading') return;
    parseUrl(targetUrl);
  }, [route]);

  useEffect(() => {
    stopTts();
  }, [article?.url]);

  useEffect(
    () => () => {
      feedRequestTrackerRef.current?.cancel();
    },
    [],
  );

  const articleStyle = useMemo(
    () => ({
      '--reader-font-size': `${settings.fontSize}px`,
      '--reader-line-height': settings.lineHeight,
      '--reader-paragraph-spacing': `${settings.paragraphSpacing}em`,
      '--reader-width': `${settings.contentWidth}px`,
    }),
    [settings],
  );

  async function parseUrl(targetUrl = url) {
    const trimmedUrl = targetUrl.trim();
    if (!trimmedUrl) {
      setError('읽을 웹페이지 URL을 입력해 주세요.');
      return;
    }

    setStatus('loading');
    setError('');
    setArticle(null);
    setSummary(null);
    setSummaryStatus('idle');
    setSummaryError('');
    setArticleInsight(null);
    setArticleInsightStatus('idle');
    setArticleInsightError('');
    setFollowUpPrompt(null);
    setFollowUpPromptStatus('idle');
    setFollowUpPromptError('');
    setCopyStatus('idle');
    setTranslation(null);
    setTranslationStatus('idle');
    setTranslationError('');
    stopTts();

    try {
      const data = await requestJson(
        `${API_BASE}/api/parse`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: trimmedUrl }),
        },
        '본문을 추출하지 못했어요.',
      );

      setArticle(data);
      setStatus('success');
    } catch (parseError) {
      setStatus('error');
      setError(parseError.message);
    }
  }

  function openReader(targetUrl) {
    let normalizedUrl;
    try {
      normalizedUrl = normalizeArticleInput(targetUrl);
    } catch (urlError) {
      setError(urlError.message);
      return;
    }

    setError('');
    sessionStorage.setItem('reader-target-url', normalizedUrl);
    setUrl(normalizedUrl);
    if (window.location.hash !== '#/reader') {
      window.location.hash = '#/reader';
      return;
    }
    setRoute('/reader');
  }

  function clearReaderState() {
    setStatus('idle');
    setError('');
    setArticle(null);
    setSummary(null);
    setSummaryStatus('idle');
    setSummaryError('');
    setArticleInsight(null);
    setArticleInsightStatus('idle');
    setArticleInsightError('');
    setFollowUpPrompt(null);
    setFollowUpPromptStatus('idle');
    setFollowUpPromptError('');
    setCopyStatus('idle');
    setTranslation(null);
    setTranslationStatus('idle');
    setTranslationError('');
    stopTts();
  }

  async function loadCategories() {
    setCategoriesStatus('loading');
    setCategoriesError('');

    try {
      const data = await requestJson(
        `${API_BASE}/api/categories`,
        {},
        '카테고리를 불러오지 못했어요.',
      );

      setCategories(data.length ? data : DEFAULT_RSS_CATEGORIES);
      setCategoriesStatus('success');

      if (!data.some((category) => category.id === newsletterCategoryId) && data[0]?.id) {
        setNewsletterCategoryId(data[0].id);
      }
      if (!data.some((category) => category.id === activeCategory) && data[0]?.id) {
        setActiveCategory(data[0].id);
      }
    } catch (categoryRequestError) {
      setCategories(DEFAULT_RSS_CATEGORIES);
      setCategoriesStatus('error');
      setCategoriesError(categoryRequestError.message);
    }
  }

  function navigateTo(nextRoute, event) {
    event.preventDefault();
    if (window.location.hash !== `#${nextRoute}`) {
      window.location.hash = nextRoute;
      return;
    }
    setRoute(nextRoute);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function loadCategory(categoryId) {
    const request = feedRequestTrackerRef.current.start();
    setActiveCategory(categoryId);
    setFeedStatus('loading');
    setFeedError('');

    try {
      const data = await requestJson(
        `${API_BASE}/api/feeds/${categoryId}`,
        { signal: request.signal },
        '카테고리 글을 불러오지 못했어요.',
      );
      if (!request.isCurrent()) return;
      setFeedItems(data.items || []);
      setFeedStatus('success');
    } catch (feedRequestError) {
      if (feedRequestError.name === 'AbortError' || !request.isCurrent()) return;
      setFeedStatus('error');
      setFeedError(feedRequestError.message);
      setFeedItems([]);
    } finally {
      request.finish();
    }
  }

  async function discoverNewsletterCandidates() {
    const label = newsletterDraft.label.trim();
    const searchHint = newsletterDraft.searchHint.trim();
    if (!label) {
      setNewsletterDraftError('카테고리 이름을 입력해 주세요.');
      return;
    }
    if (!searchHint) {
      setNewsletterDraftError('검색 힌트를 입력해 주세요.');
      return;
    }

    setNewsletterDraftStatus('loading');
    setNewsletterDraftError('');

    try {
      const data = await requestJson(
        `${API_BASE}/api/newsletter/discover`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ label, search_hint: searchHint }),
        },
        'RSS 후보를 찾지 못했어요.',
      );

      setNewsletterDraft((current) => ({
        ...current,
        candidates: data,
        selectedFeedUrls: data.length ? [data[0].feed_url] : [],
      }));
      setNewsletterModalStep(3);
      setNewsletterDraftStatus('success');
    } catch (newsletterDiscoveryError) {
      setNewsletterDraftStatus('error');
      setNewsletterDraftError(newsletterDiscoveryError.message);
    }
  }

  async function saveNewsletterCategory() {
    const selectedSources = newsletterDraft.candidates.filter((candidate) =>
      newsletterDraft.selectedFeedUrls.includes(candidate.feed_url),
    );

    if (!newsletterDraft.label.trim()) {
      setNewsletterDraftError('카테고리 이름을 입력해 주세요.');
      return;
    }
    if (!selectedSources.length) {
      setNewsletterDraftError('최소 하나의 RSS 후보를 선택해 주세요.');
      return;
    }

    setNewsletterDraftStatus('loading');
    setNewsletterDraftError('');

    try {
      const data = await requestJson(
        `${API_BASE}/api/newsletter/categories`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            label: newsletterDraft.label.trim(),
            search_hint: newsletterDraft.searchHint.trim(),
            sources: selectedSources.map((source) => ({
              source_label: source.source_label,
              feed_url: source.feed_url,
              reason: source.reason,
            })),
          }),
        },
        '카테고리를 저장하지 못했어요.',
      );

      setNewsletterModalOpen(false);
      setNewsletterModalStep(1);
      setNewsletterDraft({ label: '', searchHint: '', candidates: [], selectedFeedUrls: [] });
      setNewsletterDraftStatus('success');
      await loadCategories();
      if (data?.id) {
        setNewsletterCategoryId(data.id);
      }
    } catch (newsletterSaveError) {
      setNewsletterDraftStatus('error');
      setNewsletterDraftError(newsletterSaveError.message);
    }
  }

  async function subscribeNewsletter() {
    const email = newsletterEmail.trim();
    if (!email) {
      setNewsletterSubscribeError('이메일 주소를 입력해 주세요.');
      return;
    }
    if (!newsletterCategoryId) {
      setNewsletterSubscribeError('구독할 카테고리를 선택해 주세요.');
      return;
    }

    setNewsletterSubscribeStatus('loading');
    setNewsletterSubscribeError('');
    setNewsletterSubscribeMessage('');

    try {
      const data = await requestJson(
        `${API_BASE}/api/newsletter/subscribe`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            category_id: newsletterCategoryId,
            cadence: 'weekly',
          }),
        },
        '뉴스레터 구독에 실패했어요.',
      );

      setNewsletterSubscribeStatus('success');
      setNewsletterSubscribeMessage(data.message || '뉴스레터 구독이 완료됐어요.');
    } catch (newsletterSubscribeRequestError) {
      setNewsletterSubscribeStatus('error');
      setNewsletterSubscribeError(newsletterSubscribeRequestError.message);
    }
  }

  async function summarizeArticle() {
    if (!article) return;

    setSummaryStatus('loading');
    setSummaryError('');
    setSummary(null);
    setFollowUpPrompt(null);
    setFollowUpPromptStatus('idle');
    setFollowUpPromptError('');
    setCopyStatus('idle');
    setTranslation(null);
    setTranslationStatus('idle');
    setTranslationError('');

    try {
      const data = await requestJson(
        `${API_BASE}/api/summarize`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: article.title, text: article.text }),
        },
        'AI 요약을 만들지 못했어요.',
      );
      setSummary(data);
      setSummaryStatus('success');
    } catch (summaryRequestError) {
      setSummaryStatus('error');
      setSummaryError(summaryRequestError.message);
    }
  }

  async function generateArticleInsight() {
    if (!article) return;

    setArticleInsightStatus('loading');
    setArticleInsightError('');
    setArticleInsight(null);

    try {
      const data = await requestJson(
        `${API_BASE}/api/article-insight`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: article.title,
            text: article.text,
            source: article.site_name,
            category: activeCategory,
          }),
        },
        'AI 관찰 노트를 만들지 못했어요.',
      );
      setArticleInsight(data);
      setArticleInsightStatus('success');
    } catch (insightRequestError) {
      setArticleInsightStatus('error');
      setArticleInsightError(insightRequestError.message);
    }
  }

  async function generateFollowUpPrompt() {
    if (!article || !summary) return;

    setFollowUpPromptStatus('loading');
    setFollowUpPromptError('');
    setFollowUpPrompt(null);
    setCopyStatus('idle');

    try {
      const data = await requestJson(
        `${API_BASE}/api/follow-up-prompt`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: article.title, summary: summary.summary }),
        },
        '질문 프롬프트를 만들지 못했어요.',
      );
      setFollowUpPrompt(data.prompt);
      setFollowUpPromptStatus('success');
    } catch (followUpPromptRequestError) {
      setFollowUpPromptStatus('error');
      setFollowUpPromptError(followUpPromptRequestError.message);
    }
  }

  async function copyFollowUpPrompt() {
    if (!followUpPrompt) return;

    try {
      await navigator.clipboard.writeText(followUpPrompt);
      setCopyStatus('success');
    } catch {
      setCopyStatus('error');
    }
  }

  async function translateArticle() {
    if (!article) return;

    setTranslationStatus('loading');
    setTranslationError('');
    setTranslation(null);

    try {
      const data = await requestJson(
        `${API_BASE}/api/translate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: article.title,
            text: article.text,
            target_language: targetLanguage,
          }),
        },
        '번역을 만들지 못했어요.',
      );
      setTranslation(data);
      setTranslationStatus('success');
    } catch (translationRequestError) {
      setTranslationStatus('error');
      setTranslationError(translationRequestError.message);
    }
  }

  function ttsSupported() {
    return 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
  }

  function startTts() {
    if (!article) return;
    if (!ttsSupported()) {
      setTtsError('이 브라우저는 음성 읽기를 지원하지 않아요.');
      return;
    }

    window.speechSynthesis.cancel();
    ttsParagraphsRef.current = (article.paragraphs?.length ? article.paragraphs : [article.text]).filter(Boolean);
    ttsIndexRef.current = 0;
    setTtsError('');
    setTtsStatus('speaking');
    speakNextParagraph();
  }

  function speakNextParagraph() {
    const paragraphs = ttsParagraphsRef.current;
    const index = ttsIndexRef.current;

    if (!paragraphs.length || index >= paragraphs.length) {
      setTtsStatus('idle');
      return;
    }

    const utterance = new SpeechSynthesisUtterance(paragraphs[index]);
    utterance.lang = /[가-힣]/.test(paragraphs[index]) ? 'ko-KR' : 'en-US';
    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.onend = () => {
      ttsIndexRef.current += 1;
      speakNextParagraph();
    };
    utterance.onerror = () => {
      setTtsStatus('idle');
      setTtsError('음성 읽기 중 문제가 발생했어요.');
    };

    window.speechSynthesis.speak(utterance);
  }

  function pauseTts() {
    if (!ttsSupported()) return;
    window.speechSynthesis.pause();
    setTtsStatus('paused');
  }

  function resumeTts() {
    if (!ttsSupported()) return;
    window.speechSynthesis.resume();
    setTtsStatus('speaking');
  }

  function stopTts() {
    if (ttsSupported()) {
      window.speechSynthesis.cancel();
    }
    ttsParagraphsRef.current = [];
    ttsIndexRef.current = 0;
    setTtsStatus('idle');
  }

  function updateSetting(key, value) {
    setSettings((current) => ({ ...current, [key]: value }));
  }

  const isNewsRoute = route === '/news';
  const isUrlRoute = route === '/url';
  const isReaderRoute = route === '/reader';
  const activeCategoryLabel = categories.find((category) => category.id === activeCategory)?.label || '아이디어 레이더';
  const leadItem = feedItems[0];
  const supportingItems = feedItems.slice(1, 5);

  return (
    <main className="app-shell">
      <header className="app-header">
        <a href="#/news" className="brand-mark" onClick={(event) => navigateTo('/news', event)}>
          읽을게
        </a>
        <nav className="mode-nav" aria-label="읽기 방식">
          <a
            className={isNewsRoute ? 'active' : ''}
            href="#/news"
            onClick={(event) => navigateTo('/news', event)}
          >
            뉴스 읽기
          </a>
          <a
            className={isUrlRoute ? 'active' : ''}
            href="#/url"
            onClick={(event) => navigateTo('/url', event)}
          >
            URL로 본문 추출
          </a>
        </nav>
      </header>

      {!isReaderRoute && (
      <section id="top" className="reader-panel" aria-labelledby="app-title">
        <div className="intro">
          <p className="eyebrow">{isNewsRoute ? '오늘의 레이더' : '접근성 리더 뷰'}</p>
          <h1 id="app-title">{isNewsRoute ? '아이디어 레이더' : '읽을게'}</h1>
          <p className="lede">
            {isNewsRoute
              ? '한국 사회의 변화, 불편, 욕망이 보이는 기사를 책자처럼 골라 읽습니다.'
              : '웹페이지 URL을 입력해 광고와 메뉴를 덜어낸 본문 중심 읽기 화면으로 바꿉니다.'}
          </p>
        </div>
        {isNewsRoute && (
          <div className="issue-cover" aria-label="오늘의 아이디어 레이더 표지">
            <p>Issue · {new Intl.DateTimeFormat('ko-KR', { month: 'long', day: 'numeric' }).format(new Date())}</p>
            <h2>{activeCategoryLabel}</h2>
            <span>출처를 먼저 두고, AI는 읽을 이유와 아이디어 힌트만 여백에 적습니다.</span>
          </div>
        )}

        {isUrlRoute && (
          <>
            <form
              className="url-form"
              onSubmit={(event) => {
                event.preventDefault();
                openReader(url);
              }}
            >
              <label htmlFor="article-url">웹페이지 URL</label>
              <div className="input-row">
                <input
                  id="article-url"
                  type="text"
                  inputMode="url"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://example.com/article"
                  autoComplete="url"
                  spellCheck="false"
                />
                <button type="submit" disabled={status === 'loading'}>
                  {status === 'loading' ? '추출 중' : '읽기'}
                </button>
              </div>
            </form>
            {error && <p className="feed-error" role="alert">{error}</p>}

            <div className="sample-row" aria-label="샘플 URL">
              {SAMPLE_URLS.map((sample) => (
                <button
                  key={sample.url}
                  type="button"
                  onClick={() => {
                    setUrl(sample.url);
                    openReader(sample.url);
                  }}
                >
                  {sample.label}
                </button>
              ))}
            </div>
          </>
        )}
      </section>
      )}

      {isNewsRoute && (
        <section className="category-browser" aria-labelledby="category-title">
        <div className="section-heading">
          <p className="eyebrow">RSS 카테고리</p>
          <div className="section-heading-row">
            <h2 id="category-title">오늘의 목차</h2>
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setNewsletterModalStep(1);
                setNewsletterDraft({
                  label: '',
                  searchHint: '',
                  candidates: [],
                  selectedFeedUrls: [],
                });
                setNewsletterDraftStatus('idle');
                setNewsletterDraftError('');
                setNewsletterModalOpen(true);
              }}
            >
              카테고리 추가
            </button>
          </div>
        </div>
        {categoriesStatus === 'error' && <p className="feed-error">{categoriesError}</p>}
        <div className="category-tabs" role="tablist" aria-label="RSS 카테고리">
          {categories.map((category) => (
            <button
              key={category.id}
              type="button"
              className={activeCategory === category.id ? 'active' : ''}
              onClick={() => loadCategory(category.id)}
            >
              {category.label}
            </button>
          ))}
        </div>
        {feedStatus === 'loading' && <p className="feed-note">카테고리 글을 불러오고 있어요.</p>}
        {feedStatus === 'error' && <p className="feed-error">{feedError}</p>}
        {feedStatus === 'success' && (
          <>
            {leadItem && (
              <article className="lead-article">
                <div>
                  <p>{leadItem.source}</p>
                  <h3>{leadItem.title}</h3>
                  {leadItem.excerpt && <span>{leadItem.excerpt}</span>}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setUrl(leadItem.url);
                    openReader(leadItem.url);
                  }}
                >
                  펼쳐 읽기
                </button>
              </article>
            )}
            <div className="feed-list">
              {supportingItems.map((item, index) => (
                <article className="feed-item" key={item.url}>
                  <strong>{String(index + 2).padStart(2, '0')}</strong>
                  <div>
                    <p>{item.source}</p>
                    <h3>{item.title}</h3>
                    {item.excerpt && <span>{item.excerpt}</span>}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setUrl(item.url);
                      openReader(item.url);
                    }}
                  >
                    읽기
                  </button>
                </article>
              ))}
            </div>
          </>
        )}
        <section className="newsletter-panel" aria-labelledby="newsletter-title">
          <div className="section-heading">
            <p className="eyebrow">뉴스레터</p>
            <h2 id="newsletter-title">선택한 카테고리를 이메일로 받아보기</h2>
            <p className="newsletter-note">
              카테고리를 고른 뒤 이메일만 입력하면 구독할 수 있어요. RSS 주소는 따로 입력하지 않습니다.
            </p>
          </div>
          <div className="newsletter-form">
            <label htmlFor="newsletter-email">이메일</label>
            <input
              id="newsletter-email"
              type="email"
              value={newsletterEmail}
              onChange={(event) => setNewsletterEmail(event.target.value)}
              placeholder="name@example.com"
              autoComplete="email"
            />

            <label htmlFor="newsletter-category">카테고리</label>
            <select
              id="newsletter-category"
              value={newsletterCategoryId}
              onChange={(event) => setNewsletterCategoryId(event.target.value)}
            >
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.label}
                </option>
              ))}
            </select>

            <button type="button" onClick={subscribeNewsletter} disabled={newsletterSubscribeStatus === 'loading'}>
              {newsletterSubscribeStatus === 'loading' ? '구독 중' : '구독하기'}
            </button>
          </div>
          {newsletterSubscribeMessage && <p className="newsletter-success">{newsletterSubscribeMessage}</p>}
          {newsletterSubscribeStatus === 'error' && <p className="newsletter-error">{newsletterSubscribeError}</p>}
        </section>

        <section className="supabase-panel" aria-labelledby="supabase-title">
          <div className="section-heading">
            <p className="eyebrow">Supabase</p>
            <h2 id="supabase-title">todos 테이블을 바로 조회합니다</h2>
            <p className="newsletter-note">
              Vite 환경변수의 Supabase URL과 publishable key를 사용해 공개 테이블을 불러옵니다.
            </p>
          </div>
          {todoStatus === 'loading' && <p className="feed-note">Supabase 데이터를 불러오는 중이에요.</p>}
          {todoStatus === 'unavailable' && (
            <p className="feed-note">Supabase 설정이 없어 todos 데모만 비활성화됐어요.</p>
          )}
          {todoStatus === 'error' && <p className="feed-error">{todoError}</p>}
          {todoStatus === 'success' && (
            <div className="feed-list">
              {todoItems.length ? (
                todoItems.map((todo) => (
                  <article className="todo-item" key={todo.id}>
                    <div>
                      <p>Todo</p>
                      <h3>{todo.name || `Todo ${todo.id}`}</h3>
                      <span>ID {todo.id}</span>
                    </div>
                  </article>
                ))
              ) : (
                <p className="feed-note">todos 테이블은 비어 있어요.</p>
              )}
            </div>
          )}
        </section>
      </section>
      )}

      {isReaderRoute && status !== 'idle' && (
        <section className="toolbar" aria-label="읽기 설정">
          <Control
            label="글자"
            value={`${settings.fontSize}px`}
            onDecrease={() => updateSetting('fontSize', Math.max(15, settings.fontSize - 1))}
            onIncrease={() => updateSetting('fontSize', Math.min(24, settings.fontSize + 1))}
          />
          <Control
            label="줄간격"
            value={settings.lineHeight.toFixed(2)}
            onDecrease={() => updateSetting('lineHeight', Math.max(1.45, settings.lineHeight - 0.1))}
            onIncrease={() => updateSetting('lineHeight', Math.min(2.15, settings.lineHeight + 0.1))}
          />
          <Control
            label="문단"
            value={`${settings.paragraphSpacing.toFixed(1)}em`}
            onDecrease={() =>
              updateSetting('paragraphSpacing', Math.max(0.8, settings.paragraphSpacing - 0.2))
            }
            onIncrease={() =>
              updateSetting('paragraphSpacing', Math.min(2.4, settings.paragraphSpacing + 0.2))
            }
          />
          <Control
            label="본문 폭"
            value={`${settings.contentWidth}px`}
            onDecrease={() => updateSetting('contentWidth', Math.max(560, settings.contentWidth - 40))}
            onIncrease={() => updateSetting('contentWidth', Math.min(860, settings.contentWidth + 40))}
          />
          <div className="theme-switcher" role="group" aria-label="화면 테마">
            {['light', 'dark', 'contrast'].map((theme) => (
              <button
                key={theme}
                type="button"
                className={settings.theme === theme ? 'active' : ''}
                onClick={() => updateSetting('theme', theme)}
              >
                {theme === 'light' ? '밝게' : theme === 'dark' ? '어둡게' : '고대비'}
              </button>
            ))}
          </div>
        </section>
      )}

      {isReaderRoute && (
        <ReaderState
          status={status}
          error={error}
          article={article}
          articleStyle={articleStyle}
          summary={summary}
          summaryStatus={summaryStatus}
          summaryError={summaryError}
          articleInsight={articleInsight}
          articleInsightStatus={articleInsightStatus}
          articleInsightError={articleInsightError}
          followUpPrompt={followUpPrompt}
          followUpPromptStatus={followUpPromptStatus}
          followUpPromptError={followUpPromptError}
          copyStatus={copyStatus}
          targetLanguage={targetLanguage}
          translation={translation}
          translationStatus={translationStatus}
          translationError={translationError}
          onSummarize={summarizeArticle}
          onGenerateArticleInsight={generateArticleInsight}
          onGenerateFollowUpPrompt={generateFollowUpPrompt}
          onCopyFollowUpPrompt={copyFollowUpPrompt}
          onTargetLanguageChange={setTargetLanguage}
          onTranslate={translateArticle}
          ttsStatus={ttsStatus}
          ttsError={ttsError}
          onStartTts={startTts}
          onPauseTts={pauseTts}
          onResumeTts={resumeTts}
          onStopTts={stopTts}
        />
      )}

      {newsletterModalOpen && (
        <NewsletterCategoryModal
          step={newsletterModalStep}
          draft={newsletterDraft}
          status={newsletterDraftStatus}
          error={newsletterDraftError}
          onClose={() => {
            setNewsletterModalOpen(false);
            setNewsletterModalStep(1);
            setNewsletterDraftStatus('idle');
            setNewsletterDraftError('');
          }}
          onDraftChange={setNewsletterDraft}
          onPreviousStep={() => setNewsletterModalStep((current) => Math.max(1, current - 1))}
          onNextStep={() => setNewsletterModalStep((current) => Math.min(3, current + 1))}
          onDiscover={discoverNewsletterCandidates}
          onToggleSource={(feedUrl) => {
            setNewsletterDraft((current) => ({
              ...current,
              selectedFeedUrls: current.selectedFeedUrls.includes(feedUrl)
                ? current.selectedFeedUrls.filter((item) => item !== feedUrl)
                : [...current.selectedFeedUrls, feedUrl],
            }));
          }}
          onSave={saveNewsletterCategory}
        />
      )}
    </main>
  );
}

function Control({ label, value, onDecrease, onIncrease }) {
  return (
    <div className="control" role="group" aria-label={`${label} 조절`}>
      <span>{label}</span>
      <button type="button" onClick={onDecrease} aria-label={`${label} 줄이기`}>
        -
      </button>
      <strong>{value}</strong>
      <button type="button" onClick={onIncrease} aria-label={`${label} 키우기`}>
        +
      </button>
    </div>
  );
}

function ReaderState({
  status,
  error,
  article,
  articleStyle,
  summary,
  summaryStatus,
  summaryError,
  articleInsight,
  articleInsightStatus,
  articleInsightError,
  followUpPrompt,
  followUpPromptStatus,
  followUpPromptError,
  copyStatus,
  targetLanguage,
  translation,
  translationStatus,
  translationError,
  onSummarize,
  onGenerateArticleInsight,
  onGenerateFollowUpPrompt,
  onCopyFollowUpPrompt,
  onTargetLanguageChange,
  onTranslate,
  ttsStatus,
  ttsError,
  onStartTts,
  onPauseTts,
  onResumeTts,
  onStopTts,
}) {
  if (status === 'idle') {
    return (
      <section className="empty-state">
        <p>읽을 글을 준비하고 있어요.</p>
      </section>
    );
  }

  if (status === 'loading') {
    return (
      <section className="empty-state" aria-live="polite">
        <p>본문을 찾고 있어요.</p>
      </section>
    );
  }

  if (status === 'error') {
    return (
      <section className="error-state" role="alert">
        <h2>본문을 추출하지 못했어요</h2>
        <p>{error}</p>
      </section>
    );
  }

  return (
    <article className="reader-view" style={articleStyle}>
      <a className="source-link" href={article.url} target="_blank" rel="noreferrer">
        원본 열기
      </a>
      <p className="source-name">{article.site_name}</p>
      <h2>{article.title}</h2>
      <p className="excerpt">{article.excerpt}</p>
      <div className="article-meta">{article.word_count.toLocaleString('ko-KR')} 어절</div>
      <section className="insight-panel" aria-labelledby="insight-title">
        <div>
          <p className="summary-kicker">AI 관찰 노트</p>
          <h3 id="insight-title">읽을 이유와 아이디어 신호를 원문 옆에 메모합니다</h3>
        </div>
        <button type="button" onClick={onGenerateArticleInsight} disabled={articleInsightStatus === 'loading'}>
          {articleInsightStatus === 'loading' ? '관찰 중' : '관찰 노트 만들기'}
        </button>
        {articleInsightStatus === 'error' && <p className="summary-error">{articleInsightError}</p>}
        {articleInsightStatus === 'success' && (
          <div className="insight-result">
            <InsightList title="왜 볼 만한가" items={articleInsight.why_read} />
            <InsightList title="보이는 변화" items={articleInsight.signals} />
            <InsightList title="불편과 욕망" items={articleInsight.frictions_or_desires} />
            <InsightList title="아이디어 힌트" items={articleInsight.idea_prompts} />
            <InsightList title="주의할 점" items={articleInsight.caveats} muted />
            <p>{articleInsight.model} 사용 · AI는 원문을 대체하지 않습니다.</p>
          </div>
        )}
      </section>
      <section className="tts-panel" aria-labelledby="tts-title">
        <div>
          <p className="summary-kicker">TTS</p>
          <h3 id="tts-title">브라우저 음성으로 원문을 읽습니다</h3>
        </div>
        <div className="tts-controls">
          <button type="button" onClick={onStartTts} disabled={ttsStatus === 'speaking'}>
            {ttsStatus === 'speaking' ? '읽는 중' : '음성 읽기'}
          </button>
          {ttsStatus === 'speaking' && (
            <button type="button" onClick={onPauseTts}>
              일시정지
            </button>
          )}
          {ttsStatus === 'paused' && (
            <button type="button" onClick={onResumeTts}>
              다시 읽기
            </button>
          )}
          {(ttsStatus === 'speaking' || ttsStatus === 'paused') && (
            <button type="button" onClick={onStopTts}>
              정지
            </button>
          )}
        </div>
        {ttsError && <p className="summary-error">{ttsError}</p>}
      </section>
      <section className="summary-panel" aria-labelledby="summary-title">
        <div>
          <p className="summary-kicker">AI 요약</p>
          <h3 id="summary-title">원문을 바꾸지 않고 핵심만 압축합니다</h3>
        </div>
        <button type="button" onClick={onSummarize} disabled={summaryStatus === 'loading'}>
          {summaryStatus === 'loading' ? '요약 중' : '요약 만들기'}
        </button>
        {summaryStatus === 'error' && <p className="summary-error">{summaryError}</p>}
        {summaryStatus === 'success' && (
          <div className="summary-result">
            <ul>
              {summary.summary.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <div className="summary-actions">
              <p>{summary.model} 사용</p>
              <button
                type="button"
                onClick={onGenerateFollowUpPrompt}
                disabled={followUpPromptStatus === 'loading'}
              >
                {followUpPromptStatus === 'loading' ? '질문 준비 중' : '질문 생성하기'}
              </button>
            </div>
            {followUpPromptStatus === 'error' && (
              <p className="summary-error">{followUpPromptError}</p>
            )}
            {followUpPromptStatus === 'success' && (
              <div className="follow-up-prompt">
                <div className="follow-up-prompt-header">
                  <strong>복사용 질문 프롬프트</strong>
                  <button type="button" onClick={onCopyFollowUpPrompt}>
                    {copyStatus === 'success' ? '복사됨' : '복사'}
                  </button>
                </div>
                <pre>{followUpPrompt}</pre>
                {copyStatus === 'error' && (
                  <p className="summary-error">브라우저에서 복사를 허용하지 않았어요.</p>
                )}
              </div>
            )}
          </div>
        )}
      </section>
      <section className="summary-panel" aria-labelledby="translate-title">
        <div>
          <p className="summary-kicker">AI 번역</p>
          <h3 id="translate-title">필요할 때만 본문 번역을 생성합니다</h3>
        </div>
        <div className="translation-controls">
          <label htmlFor="target-language">번역 언어</label>
          <select
            id="target-language"
            value={targetLanguage}
            onChange={(event) => onTargetLanguageChange(event.target.value)}
          >
            {TRANSLATE_TARGETS.map((target) => (
              <option key={target.value} value={target.value}>
                {target.label}
              </option>
            ))}
          </select>
          <button type="button" onClick={onTranslate} disabled={translationStatus === 'loading'}>
            {translationStatus === 'loading' ? '번역 중' : '번역하기'}
          </button>
        </div>
        {translationStatus === 'error' && <p className="summary-error">{translationError}</p>}
        {translationStatus === 'success' && (
          <div className="translation-result">
            <p>
              {translation.target_language} · {translation.model}
            </p>
            <div>
              {(translation.paragraphs?.length ? translation.paragraphs : [translation.translated_text]).map(
                (paragraph, index) => (
                  <p key={`${paragraph.slice(0, 16)}-${index}`}>{paragraph}</p>
                ),
              )}
            </div>
          </div>
        )}
      </section>
      <div className="article-body">
        {(article.paragraphs?.length ? article.paragraphs : article.text.split(/\n{2,}/)).map((paragraph, index) => (
          <p key={`${paragraph.slice(0, 16)}-${index}`}>{paragraph}</p>
        ))}
      </div>
    </article>
  );
}

function InsightList({ title, items, muted = false }) {
  if (!items?.length) return null;

  return (
    <section className={muted ? 'insight-block muted' : 'insight-block'}>
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function NewsletterCategoryModal({
  step,
  draft,
  status,
  error,
  onClose,
  onDraftChange,
  onNextStep,
  onPreviousStep,
  onDiscover,
  onToggleSource,
  onSave,
}) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="newsletter-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">뉴스레터 카테고리 추가</p>
            <h2 id="newsletter-modal-title">검색 힌트로 RSS 후보를 찾습니다</h2>
          </div>
          <button type="button" className="secondary-button" onClick={onClose}>
            닫기
          </button>
        </div>

        <div className="step-indicator" aria-label="카테고리 추가 단계">
          <span className={step === 1 ? 'active' : ''}>1. 이름</span>
          <span className={step === 2 ? 'active' : ''}>2. 힌트</span>
          <span className={step === 3 ? 'active' : ''}>3. 후보</span>
        </div>

        <div className="modal-body">
          {step === 1 && (
            <section className="modal-step">
              <label htmlFor="newsletter-category-label">카테고리 이름</label>
              <input
                id="newsletter-category-label"
                type="text"
                value={draft.label}
                onChange={(event) =>
                  onDraftChange((current) => ({
                    ...current,
                    label: event.target.value,
                    candidates: [],
                    selectedFeedUrls: [],
                  }))
                }
                placeholder="스타트업, 디자인, AI"
              />
              <div className="modal-actions">
                <button type="button" onClick={onClose}>
                  취소
                </button>
                <button type="button" onClick={onNextStep} disabled={!draft.label.trim()}>
                  다음
                </button>
              </div>
            </section>
          )}

          {step === 2 && (
            <section className="modal-step">
              <label htmlFor="newsletter-search-hint">참고할 사이트/키워드</label>
              <input
                id="newsletter-search-hint"
                type="text"
                value={draft.searchHint}
                onChange={(event) =>
                  onDraftChange((current) => ({
                    ...current,
                    searchHint: event.target.value,
                    candidates: [],
                    selectedFeedUrls: [],
                  }))
                }
                placeholder="TechCrunch, GeekNews, AI 스타트업, VC 뉴스"
              />
              <p className="modal-help">
                생각나는 블로그 이름, 사이트 이름, 관심 키워드를 적으면 RSS 후보를 찾아봅니다.
              </p>
              <div className="modal-actions">
                <button type="button" onClick={onPreviousStep}>
                  이전
                </button>
                <button type="button" onClick={onDiscover} disabled={status === 'loading' || !draft.searchHint.trim()}>
                  {status === 'loading' ? '찾는 중' : '후보 찾기'}
                </button>
              </div>
            </section>
          )}

          {step === 3 && (
            <section className="modal-step">
              <div className="modal-candidate-list">
                {draft.candidates.length ? (
                  draft.candidates.map((candidate) => {
                    const checked = draft.selectedFeedUrls.includes(candidate.feed_url);
                    return (
                      <label key={candidate.feed_url} className={`candidate-card ${checked ? 'active' : ''}`}>
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => onToggleSource(candidate.feed_url)}
                        />
                        <div>
                          <strong>{candidate.source_label}</strong>
                          <p>{candidate.reason}</p>
                          <span>{candidate.feed_url}</span>
                        </div>
                      </label>
                    );
                  })
                ) : (
                  <p className="modal-help">선택할 후보가 없어요. 이전 단계로 돌아가 검색 힌트를 수정해 보세요.</p>
                )}
              </div>
              <div className="modal-actions">
                <button type="button" onClick={onPreviousStep}>
                  이전
                </button>
                <button type="button" onClick={onSave} disabled={status === 'loading' || !draft.selectedFeedUrls.length}>
                  {status === 'loading' ? '저장 중' : '저장'}
                </button>
              </div>
            </section>
          )}

          {error && <p className="modal-error">{error}</p>}
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
