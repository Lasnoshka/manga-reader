const API = "/api/v1";
const TOKEN_KEY = "mr_token";

const api = {
    token() { return localStorage.getItem(TOKEN_KEY); },
    setToken(t) { localStorage.setItem(TOKEN_KEY, t); },
    clearToken() { localStorage.removeItem(TOKEN_KEY); },

    async request(path, opts = {}) {
        const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
        const token = api.token();
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(`${API}${path}`, { ...opts, headers });
        if (res.status === 204) return null;

        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            const msg = data?.error?.message || `HTTP ${res.status}`;
            throw new Error(msg);
        }
        return data;
    },

    get(p) { return api.request(p); },
    post(p, body) { return api.request(p, { method: "POST", body: JSON.stringify(body) }); },
    put(p, body) { return api.request(p, { method: "PUT", body: JSON.stringify(body) }); },
    patch(p, body) { return api.request(p, { method: "PATCH", body: JSON.stringify(body) }); },
    del(p) { return api.request(p, { method: "DELETE" }); },

    async loginForm(username, password) {
        const body = new URLSearchParams({ username, password });
        const res = await fetch(`${API}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data?.error?.message || `HTTP ${res.status}`);
        return data;
    },
};

function formatDate(isoString) {
    if (!isoString) return "";
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "";
    const now = new Date();
    const diffMs = now - d;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "только что";
    if (diffMin < 60) return `${diffMin} мин назад`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} ч назад`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 7) return `${diffDay} дн назад`;
    return d.toLocaleDateString("ru-RU");
}

const BOOKMARK_FOLDERS = [
    { value: "reading",   label: "Читаю" },
    { value: "planned",   label: "В планах" },
    { value: "completed", label: "Прочитано" },
    { value: "favorite",  label: "Любимое" },
    { value: "dropped",   label: "Брошено" },
];

function folderLabel(value) {
    return BOOKMARK_FOLDERS.find(f => f.value === value)?.label || value;
}

document.addEventListener("alpine:init", () => {
    Alpine.store("auth", {
        user: null,
        ready: false,
        async load() {
            if (!api.token()) { this.ready = true; return; }
            try {
                this.user = await api.get("/auth/me");
            } catch (e) {
                api.clearToken();
                this.user = null;
            } finally {
                this.ready = true;
            }
        },
        logout() {
            api.clearToken();
            this.user = null;
            window.location.href = "/";
        },
    });
    Alpine.store("auth").load();
});

/* ===== Root: shared user state ===== */
function appRoot() {
    return {
        get user() { return Alpine.store("auth").user; },
        init() {},
        logout() { Alpine.store("auth").logout(); },
    };
}

/* ===== Auth forms ===== */
function loginForm() {
    return {
        username: "",
        password: "",
        loading: false,
        error: "",
        async submit() {
            this.error = "";
            this.loading = true;
            try {
                const data = await api.loginForm(this.username, this.password);
                api.setToken(data.access_token);
                window.location.href = "/";
            } catch (e) {
                this.error = e.message;
            } finally {
                this.loading = false;
            }
        },
    };
}

function registerForm() {
    return {
        username: "",
        email: "",
        password: "",
        loading: false,
        error: "",
        async submit() {
            this.error = "";
            this.loading = true;
            try {
                const data = await api.post("/auth/register", {
                    username: this.username,
                    email: this.email,
                    password: this.password,
                });
                api.setToken(data.access_token);
                window.location.href = "/";
            } catch (e) {
                this.error = e.message;
            } finally {
                this.loading = false;
            }
        },
    };
}

/* ===== Manga page: like + bookmark ===== */
function mangaPage(mangaId, initialLikes) {
    return {
        mangaId,
        likesCount: initialLikes,
        liked: false,
        bookmark: null,
        bookmarkFolders: BOOKMARK_FOLDERS,
        get user() { return Alpine.store("auth").user; },

        async init() {
            try {
                const status = await api.get(`/manga/${this.mangaId}/like/`);
                this.likesCount = status.likes_count;
                this.liked = status.liked;
            } catch (e) { /* ignore */ }

            if (api.token()) {
                try {
                    const bookmarks = await api.get("/bookmarks/");
                    const found = bookmarks.find(b => b.manga_id === this.mangaId);
                    this.bookmark = found ? found.folder : null;
                } catch (e) { /* ignore */ }
            }
        },

        async toggleLike() {
            if (!api.token()) { window.location.href = "/login"; return; }
            try {
                const res = this.liked
                    ? await api.del(`/manga/${this.mangaId}/like/`)
                    : await api.post(`/manga/${this.mangaId}/like/`, {});
                this.likesCount = res.likes_count;
                this.liked = res.liked;
            } catch (e) { alert(e.message); }
        },

        bookmarkLabel() {
            return this.bookmark ? folderLabel(this.bookmark) : "+ В закладки";
        },

        async setBookmark(folder) {
            if (!api.token()) { window.location.href = "/login"; return; }
            try {
                if (this.bookmark) {
                    await api.patch(`/bookmarks/${this.mangaId}`, { folder });
                } else {
                    await api.post("/bookmarks/", { manga_id: this.mangaId, folder });
                }
                this.bookmark = folder;
            } catch (e) { alert(e.message); }
        },

        async removeBookmark() {
            try {
                await api.del(`/bookmarks/${this.mangaId}`);
                this.bookmark = null;
            } catch (e) { alert(e.message); }
        },
    };
}

/* ===== Comments block (manga-level or chapter-level) ===== */
function commentsBlock(mangaId, chapterId) {
    return {
        mangaId,
        chapterId,
        items: [],
        total: 0,
        loading: false,
        posting: false,
        newText: "",
        get user() { return Alpine.store("auth").user; },
        formatDate,

        async load() {
            this.loading = true;
            try {
                const params = new URLSearchParams({ parent_id: "0", size: "50" });
                if (this.mangaId) params.set("manga_id", String(this.mangaId));
                if (this.chapterId) params.set("chapter_id", String(this.chapterId));
                const data = await api.get(`/comments/?${params}`);
                this.items = data.items;
                this.total = data.total;
            } catch (e) { console.warn(e); }
            this.loading = false;
        },

        async submit() {
            if (!this.newText.trim()) return;
            this.posting = true;
            try {
                const body = { content: this.newText.trim() };
                if (this.mangaId) body.manga_id = this.mangaId;
                if (this.chapterId) body.chapter_id = this.chapterId;
                const created = await api.post("/comments/", body);
                this.items = [created, ...this.items];
                this.total += 1;
                this.newText = "";
            } catch (e) { alert(e.message); }
            this.posting = false;
        },

        async remove(id) {
            if (!confirm("Удалить комментарий?")) return;
            try {
                await api.del(`/comments/${id}`);
                this.items = this.items.filter(c => c.id !== id);
                this.total -= 1;
            } catch (e) { alert(e.message); }
        },
    };
}

/* ===== Reader: autosave progress on scroll ===== */
function readerBar(mangaId, chapterId, totalPages, prevId, nextId) {
    return {
        mangaId, chapterId, totalPages, prevId, nextId,
        currentPage: 1,
        saveTimer: null,
        lastSaved: 0,
        drawerOpen: false,

        init() {
            window.addEventListener("scroll", () => this.onScroll(), { passive: true });
            window.addEventListener("beforeunload", () => this.flushSave());
            this.onScroll();
        },

        onScroll() {
            const pages = document.querySelectorAll(".reader-page");
            const viewMid = window.scrollY + window.innerHeight * 0.4;
            let current = 1;
            for (const el of pages) {
                if (el.offsetTop <= viewMid) current = parseInt(el.dataset.page, 10);
            }
            if (current !== this.currentPage) {
                this.currentPage = current;
                this.scheduleSave();
            }
        },

        scheduleSave() {
            if (!api.token()) return;
            clearTimeout(this.saveTimer);
            this.saveTimer = setTimeout(() => this.flushSave(), 1500);
        },

        flushSave() {
            if (!api.token()) return;
            if (this.currentPage === this.lastSaved) return;
            const payload = {
                manga_id: this.mangaId,
                chapter_id: this.chapterId,
                page_number: this.currentPage,
            };
            this.lastSaved = this.currentPage;
            api.put("/progress/", payload).catch(() => {});
        },
    };
}

/* ===== Admin: manga CRUD ===== */
const EMPTY_FORM = {
    title: "", author: "", cover_image: "",
    description: "", rating: null, genresText: "",
};

function adminManga() {
    return {
        items: [], total: 0, pagesTotal: 1,
        page: 1, size: 20,
        query: "",
        loading: false,
        formOpen: false,
        saving: false,
        editingId: null,
        error: "",
        form: { ...EMPTY_FORM },
        get user() { return Alpine.store("auth").user; },

        async init() {
            for (let i = 0; i < 40 && !Alpine.store("auth").ready; i++) {
                await new Promise(r => setTimeout(r, 50));
            }
            if (this.user?.role !== "admin") return;
            await this.load();
        },

        async load() {
            this.loading = true;
            const params = new URLSearchParams({
                page: this.page, size: this.size,
                sort_by: "created_at", sort_desc: "true",
            });
            if (this.query.trim()) params.set("title_contains", this.query.trim());
            try {
                const data = await api.get(`/manga/?${params}`);
                this.items = data.items;
                this.total = data.total;
                this.pagesTotal = Math.max(1, data.pages || 1);
            } catch (e) {
                alert("Не удалось загрузить: " + e.message);
            }
            this.loading = false;
        },

        goto(p) {
            if (p < 1 || p > this.pagesTotal || p === this.page) return;
            this.page = p;
            this.load();
        },

        openCreate() {
            this.editingId = null;
            this.form = { ...EMPTY_FORM };
            this.error = "";
            this.formOpen = true;
        },

        openEdit(m) {
            this.editingId = m.id;
            this.form = {
                title: m.title || "",
                author: m.author || "",
                cover_image: m.cover_image || "",
                description: m.description || "",
                rating: m.rating ?? null,
                genresText: (m.genres || []).map(g => g.name).join(", "),
            };
            this.error = "";
            this.formOpen = true;
        },

        closeForm() {
            this.formOpen = false;
            this.error = "";
        },

        async submit() {
            this.saving = true;
            this.error = "";
            const payload = {
                title: this.form.title,
                description: this.form.description,
                cover_image: this.form.cover_image || null,
                author: this.form.author || null,
                genres: this.form.genresText.split(",").map(s => s.trim()).filter(Boolean),
            };
            if (this.editingId && this.form.rating !== null && this.form.rating !== "") {
                payload.rating = Number(this.form.rating);
            }
            try {
                if (this.editingId) {
                    await api.patch(`/manga/${this.editingId}`, payload);
                } else {
                    await api.post("/manga/", payload);
                }
                this.closeForm();
                await this.load();
            } catch (e) {
                this.error = e.message;
            }
            this.saving = false;
        },

        async remove(m) {
            if (!confirm(`Удалить «${m.title}»? Действие нельзя отменить.`)) return;
            try {
                await api.del(`/manga/${m.id}`);
                await this.load();
            } catch (e) {
                alert("Ошибка: " + e.message);
            }
        },
    };
}

/* ===== Profile page ===== */
function profilePage() {
    return {
        tab: "bookmarks",
        bookmarkFolder: "",
        folders: BOOKMARK_FOLDERS,
        bookmarks: [],
        progress: [],
        loading: false,
        get user() { return Alpine.store("auth").user; },
        folderLabel,

        async init() {
            for (let i = 0; i < 30 && !Alpine.store("auth").ready; i++) {
                await new Promise(r => setTimeout(r, 50));
            }
            if (!Alpine.store("auth").user) return;
            await this.loadBookmarks();
            await this.loadProgress();
        },

        async setFolder(value) {
            this.bookmarkFolder = value;
            await this.loadBookmarks();
        },

        async loadBookmarks() {
            this.loading = true;
            try {
                const path = this.bookmarkFolder
                    ? `/bookmarks/?folder=${this.bookmarkFolder}`
                    : "/bookmarks/";
                const items = await api.get(path);
                this.bookmarks = await this.attachManga(items);
            } catch (e) { console.warn(e); }
            this.loading = false;
        },

        async loadProgress() {
            try {
                const items = await api.get("/progress/");
                this.progress = await this.attachManga(items);
            } catch (e) { console.warn(e); }
        },

        async attachManga(items) {
            if (!items.length) return items;
            const ids = [...new Set(items.map(i => i.manga_id))];
            const mangaMap = {};
            await Promise.all(ids.map(async id => {
                try { mangaMap[id] = await api.get(`/manga/${id}`); }
                catch { mangaMap[id] = null; }
            }));
            return items.map(i => ({ ...i, manga: mangaMap[i.manga_id] }));
        },
    };
}
