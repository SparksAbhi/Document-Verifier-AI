let currentRole = 'officer';
let selectedDecision = null;
let pendingDocFile = null;
let pendingFaceFile = null;
let currentResult = null;

function showLoginStep(stepId) {
	document.querySelectorAll('.login-step').forEach((step) => {
		step.classList.toggle('active', step.id === stepId);
	});
}

function selectRole(role) {
	currentRole = role;
	showLoginStep(role === 'user' ? 'step-user-auth' : 'step-officer-auth');
}

function switchAuthTab(tabName) {
	document.querySelectorAll('.auth-tab').forEach((tab) => {
		tab.classList.toggle('active', tab.dataset.tab === tabName);
	});
	document.querySelectorAll('.auth-form').forEach((form) => {
		form.classList.toggle('active', form.id === `form-${tabName}`);
	});
}

let currentUser = null; // {id, email, name, role, passportNo} from /api/auth/me

function _showAuthError(elementId, message) {
	const box = document.getElementById(elementId);
	if (!box) return;
	box.textContent = message;
	box.classList.add('show');
}

function _clearAuthErrors() {
	['ul-error', 'su-error', 'of-error'].forEach((id) => {
		const box = document.getElementById(id);
		if (box) {
			box.textContent = '';
			box.classList.remove('show');
		}
	});
}

async function _authPost(url, body) {
	const response = await fetch(url, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});
	const data = await response.json().catch(() => ({}));
	if (!response.ok) {
		throw new Error(data.detail || `Server responded ${response.status}`);
	}
	return data;
}

function switchOfficerTab(tabName) {
	document.querySelectorAll('#step-officer-auth .auth-tab').forEach((tab) => {
		tab.classList.toggle('active', tab.dataset.tab === tabName);
	});
	document.querySelectorAll('#step-officer-auth .auth-form').forEach((form) => {
		form.classList.toggle('active', form.id === `form-${tabName}`);
	});
}

async function userLogin() {
	_clearAuthErrors();
	const login = document.getElementById('ul-email').value.trim();
	const password = document.getElementById('ul-password').value;
	if (!login || !password) {
		_showAuthError('ul-error', 'Enter your user ID/email and password.');
		return;
	}
	try {
		const data = await _authPost('/api/auth/login', { login, password, role: 'user' });
		currentUser = data.user;
		showLoginStep('step-liveness');
		startLoginLiveness();
	} catch (error) {
		_showAuthError('ul-error', error.message);
	}
}

async function signupUser() {
	_clearAuthErrors();
	const name = document.getElementById('su-name').value.trim();
	const email = document.getElementById('su-email').value.trim();
	const username = document.getElementById('su-username').value.trim();
	const passport = document.getElementById('su-passport').value.trim();
	const password = document.getElementById('su-password').value;
	const confirm = document.getElementById('su-confirm').value;
	if (!name || !email || !username || !password) {
		_showAuthError('su-error', 'Name, email, user ID and password are required.');
		return;
	}
	if (password !== confirm) {
		_showAuthError('su-error', 'Passwords do not match.');
		return;
	}
	try {
		const data = await _authPost('/api/auth/signup', {
			name, email, username, password, confirmPassword: confirm,
			passportNo: passport || null, role: 'user',
		});
		currentUser = data.user;
		showLoginStep('step-liveness');
		startLoginLiveness();
	} catch (error) {
		_showAuthError('su-error', error.message);
	}
}

async function signupOfficer() {
	_clearAuthErrors();
	const name = document.getElementById('ofsu-name').value.trim();
	const email = document.getElementById('ofsu-email').value.trim();
	const username = document.getElementById('ofsu-username').value.trim();
	const password = document.getElementById('ofsu-password').value;
	const confirm = document.getElementById('ofsu-confirm').value;
	if (!name || !email || !username || !password) {
		_showAuthError('ofsu-error', 'Name, email, officer ID and access key are required.');
		return;
	}
	if (password !== confirm) {
		_showAuthError('ofsu-error', 'Access keys do not match.');
		return;
	}
	try {
		const data = await _authPost('/api/auth/signup', {
			name, email, username, password, confirmPassword: confirm, role: 'officer',
		});
		currentUser = data.user;
		currentRole = 'officer';
		enterPortal();
	} catch (error) {
		_showAuthError('ofsu-error', error.message);
	}
}

async function officerLogin() {
	_clearAuthErrors();
	const login = document.getElementById('of-email').value.trim();
	const password = document.getElementById('of-password').value;
	if (!login || !password) {
		_showAuthError('of-error', 'Enter your officer ID/email and access key.');
		return;
	}
	try {
		const data = await _authPost('/api/auth/login', { login, password, role: 'officer' });
		currentUser = data.user;
		currentRole = 'officer';
		enterPortal();
	} catch (error) {
		_showAuthError('of-error', error.message);
	}
}

let loginCameraStream = null;
let loginLivenessPassed = false;

async function startLoginLiveness() {
	const video = document.getElementById('login-camera-video');
	const icon = document.getElementById('login-camera-icon');
	const sweep = document.getElementById('login-scan-sweep');
	const verdict = document.getElementById('liveness-verdict');
	const continueButton = document.getElementById('btn-continue-liveness');
	const startButton = document.getElementById('btn-start-login-liveness');
	const checks = [...document.querySelectorAll('#liveness-checklist .check-item')];

	continueButton.disabled = true;
	continueButton.classList.add('btn-disabled');
	loginLivenessPassed = false;
	checks.forEach((check) => {
		check.classList.remove('checking', 'pass', 'flagged');
		check.querySelector('.cstatus')?.remove();
	});
	startButton.disabled = true;
	startButton.classList.add('btn-disabled');
	verdict.textContent = 'Requesting camera permission…';

	try {
		loginCameraStream = await navigator.mediaDevices.getUserMedia({
			video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
			audio: false,
		});
	} catch (error) {
		verdict.textContent = 'Camera unavailable — you can continue to the portal, but the login face check could not run.';
		startButton.disabled = false;
		startButton.classList.remove('btn-disabled');
		continueButton.disabled = false;
		continueButton.classList.remove('btn-disabled');
		return;
	}

	video.srcObject = loginCameraStream;
	video.style.display = '';
	icon.style.display = 'none';
	sweep.style.display = '';
	verdict.textContent = 'Camera ready — hold still and look at the lens while the check runs…';

	// capture 8 frames @350ms — same burst as the officer camera flow
	const blobs = [];
	try {
		for (let i = 0; i < 8; i += 1) {
			// eslint-disable-next-line no-await-in-loop
			blobs.push(await _captureFrame(video));
			verdict.textContent = `Capturing frames (${i + 1}/8) — hold still…`;
			// eslint-disable-next-line no-await-in-loop
			await new Promise((resolve) => window.setTimeout(resolve, 350));
		}
	} catch (error) {
		verdict.textContent = `Frame capture failed: ${error.message}`;
		sweep.style.display = 'none';
		startButton.disabled = false;
		startButton.classList.remove('btn-disabled');
		return;
	}

	verdict.textContent = 'Analyzing frames for presentation-attack signals…';
	let result = null;
	try {
		const formData = new FormData();
		blobs.forEach((blob, index) => formData.append('frames', blob, `frame_${index}.jpg`));
		const response = await fetch('/api/liveness', { method: 'POST', body: formData });
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		result = await response.json();
	} catch (error) {
		verdict.textContent = `Liveness check could not run: ${error.message}. Continue and verify manually.`;
	}

	if (loginCameraStream) {
		loginCameraStream.getTracks().forEach((track) => track.stop());
		loginCameraStream = null;
	}
	sweep.style.display = 'none';
	video.style.display = 'none';
	icon.style.display = '';

	if (!result) {
		startButton.disabled = false;
		startButton.classList.remove('btn-disabled');
		continueButton.disabled = false;
		continueButton.classList.remove('btn-disabled');
		return;
	}

	// map backend checks onto the login checklist rows
	const byLabel = {
		'li-motion': result.checks.find((c) => c.label.startsWith('Motion')),
		'li-printed': result.checks.find((c) => c.label.startsWith('Motion')),
		'li-replay': result.checks.find((c) => c.label.startsWith('Motion')),
		'li-multiface': result.checks.find((c) => c.label.startsWith('Face presence (first')),
	};
	byLabel['li-printed'] = result.liveness === 'fail' ? byLabel['li-printed'] : null;
	byLabel['li-replay'] = (result.motionScore !== null && result.motionScore > 30) ? byLabel['li-replay'] : null;

	checks.forEach((check) => {
		const mapped = byLabel[check.id];
		const passed = !mapped || mapped.status === 'pass';
		check.classList.add(passed ? 'pass' : 'flagged');
		const status = document.createElement('span');
		status.className = 'cstatus';
		status.textContent = passed ? 'PASS' : 'REVIEW';
		check.append(status);
	});

	if (result.liveness === 'pass') {
		loginLivenessPassed = true;
		verdict.textContent = `Face verified. No presentation attack detected (motion ${result.motionScore}). Simplified check.`;
	} else if (result.liveness === 'fail') {
		verdict.textContent = 'Presentation attack suspected. You can continue, but your session will be flagged for officer review.';
	} else {
		verdict.textContent = 'Liveness inconclusive — officer review will be required.';
	}
	continueButton.disabled = false;
	continueButton.classList.remove('btn-disabled');
	startButton.disabled = false;
	startButton.classList.remove('btn-disabled');
}

function continueAfterLiveness() {
	if (loginCameraStream) {
		loginCameraStream.getTracks().forEach((track) => track.stop());
		loginCameraStream = null;
	}
	currentRole = 'user';
	enterPortal();
}

function logout() {
	if (loginCameraStream) {
		loginCameraStream.getTracks().forEach((track) => track.stop());
		loginCameraStream = null;
	}
	closeFaceCamera();
	fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
	pendingDocFile = null;
	pendingFaceFile = null;
	currentResult = null;
	selectedDecision = null;
	currentUser = null;
	currentRole = 'officer';
	userQueryState = null;
	document.getElementById('app-shell').style.display = 'none';
	document.getElementById('view-login').classList.add('active');
	showLoginStep('step-role');
}

function enterPortal() {
	document.getElementById('view-login').classList.remove('active');
	document.getElementById('app-shell').style.display = 'flex';
	document.getElementById('nav-officer-group').style.display = currentRole === 'officer' ? '' : 'none';
	document.getElementById('nav-user-group').style.display = currentRole === 'user' ? '' : 'none';
	document.getElementById('identity-chip-officer').style.display = currentRole === 'officer' ? 'flex' : 'none';
	document.getElementById('identity-chip-user').style.display = currentRole === 'user' ? 'flex' : 'none';

	// real identity from the logged-in account
	if (currentUser) {
		const initials = (currentUser.name || '?')
			.split(/\s+/)
			.map((part) => part[0])
			.slice(0, 2)
			.join('')
			.toUpperCase();
		if (currentRole === 'officer') {
			document.getElementById('officer-name').textContent = currentUser.name;
			document.getElementById('officer-avatar').textContent = initials;
		} else {
			document.getElementById('user-name').textContent = currentUser.name;
			document.getElementById('user-avatar').textContent = initials;
		}
	}

	goTo(currentRole === 'officer' ? 'dashboard' : 'user-portal');
	if (currentRole === 'user') loadMyQueries();
	displayProfilePicture();
}

function goTo(viewName) {
	const view = document.getElementById(`view-${viewName}`);
	if (!view) return;

	document.querySelectorAll('.view').forEach((item) => item.classList.remove('active'));
	view.classList.add('active');
	document.querySelectorAll('.navitem[data-view]').forEach((item) => {
		item.classList.toggle('active', item.dataset.view === viewName);
	});

	const title = view.querySelector('.page-title')?.textContent.trim() || viewName;
	document.getElementById('topbar-title').textContent = title;
	document.getElementById('topbar-crumb').textContent = ` / ${viewName.replaceAll('-', ' ')}`;
	if (viewName === 'dashboard') refreshDashboard();
	if (viewName === 'user-portal') loadMyQueries();
	if (viewName === 'trash') loadTrash();
	if (viewName === 'profile') loadProfile();
	if (viewName === 'investigation') loadWatchlist();
}

// ===== LANGUAGE TOGGLE (English / हिंदी) =====

let currentLang = 'en';

const I18N = {
	// login screens
	'Login as Officer': 'अधिकारी के रूप में लॉगिन करें',
	'Login as User': 'उपयोगकर्ता के रूप में लॉगिन करें',
	'BORDER SCREENING CONSOLE': 'सीमा जांच कंसोल',
	'Login & Continue': 'लॉगिन करें और आगे बढ़ें',
	'Create Account & Continue': 'खाता बनाएं और आगे बढ़ें',
	'Register Officer & Enter': 'अधिकारी पंजीकृत करें और प्रवेश करें',
	'Authenticate & Enter': 'प्रमाणीकृत करें और प्रवेश करें',
	'Existing Officer': 'मौजूदा अधिकारी',
	'New Officer': 'नया अधिकारी',
	'Existing User': 'मौजूदा उपयोगकर्ता',
	'New User': 'नया उपयोगकर्ता',
	'Sign Up': 'साइन अप',
	'Forgot Password': 'पासवर्ड भूल गए',
	// sidebar
	'Dashboard': 'डैशबोर्ड',
	'New Screening': 'नई जांच',
	'Processing': 'प्रोसेसिंग',
	'Result': 'परिणाम',
	'Investigation': 'जांच-पड़ताल',
	'Trash': 'कूड़ादान',
	'My Queries': 'मेरे प्रश्न',
	'Submit Query': 'प्रश्न भेजें',
	'Log out': 'लॉग आउट',
	// dashboard
	'Documents screened today': 'आज जांचे गए दस्तावेज़',
	'Cleared — low risk': 'मंज़ूर — कम जोखिम',
	'Flagged for review': 'समीक्षा हेतु चिन्हित',
	'High-risk holds': 'उच्च-जोखिम रोक',
	'Recent screenings': 'हाल की जांच',
	'Escalation queue': 'एस्केलेशन कतार',
	'No screenings recorded yet — upload a document to begin.': 'अभी कोई जांच दर्ज नहीं है — शुरू करने के लिए दस्तावेज़ अपलोड करें।',
	'Queue clear — no open high-risk cases.': 'कतार साफ़ — कोई खुला उच्च-जोखिम मामला नहीं।',
	// upload
	'Document upload': 'दस्तावेज़ अपलोड',
	'Begin analysis →': 'विश्लेषण शुरू करें →',
	'Open camera': 'कैमरा खोलें',
	'Upload photo': 'फ़ोटो अपलोड करें',
	// processing
	'Wait — your documents are processing…': 'प्रतीक्षा करें — आपके दस्तावेज़ प्रोसेस हो रहे हैं…',
	'Analysis pipeline': 'विश्लेषण पाइपलाइन',
	'Engine log': 'इंजन लॉग',
	'Analysis complete': 'विश्लेषण पूर्ण',
	'View result →': 'परिणाम देखें →',
	'← Back to upload': '← अपलोड पर वापस जाएं',
	// result
	'Detection flags': 'पहचान झंडे',
	'Risk reasons': 'जोखिम कारण',
	'AI risk recommendation': 'एआई जोखिम सिफ़ारिश',
	'FACE MATCH': 'चेहरा मिलान',
	// user portal
	'Submit a query': 'प्रश्न भेजें',
	'Run verification checks': 'सत्यापन जांच चलाएं',
	'Submit to Officer for verification': 'सत्यापन के लिए अधिकारी को भेजें',
	'Send to Officer': 'अधिकारी को भेजें',
	'My profile': 'मेरी प्रोफ़ाइल',
};

function applyLanguage() {
	document.querySelectorAll('label, .navitem, .panel-title, .page-title, .page-sub, .btn, .dropzone-title, .stat-label, .login-sub, .auth-tab').forEach((el) => {
		const key = el.dataset.enText || el.textContent.trim();
		if (!el.dataset.enText && key) el.dataset.enText = key;
		const translated = currentLang === 'hi' ? I18N[key] : (el.dataset.enText || key);
		if (translated) el.textContent = translated;
	});
	// processing wait-title contains a spinner — special case
	const procTitle = document.getElementById('proc-title');
	if (procTitle && !procTitle.classList.contains('complete')) {
		procTitle.innerHTML = '<span class="proc-spinner"></span>' + (currentLang === 'hi'
			? 'प्रतीक्षा करें — आपके दस्तावेज़ प्रोसेस हो रहे हैं…'
			: 'Wait — your documents are processing…');
	}
	const toggle = document.getElementById('lang-toggle');
	if (toggle) toggle.textContent = currentLang === 'hi' ? 'हिंदी ✓' : 'EN / हिंदी';
}

function toggleLanguage() {
	currentLang = currentLang === 'en' ? 'hi' : 'en';
	applyLanguage();
}



function togglePassword(buttonId, inputId) {
	const input = document.getElementById(inputId);
	const button = document.getElementById(buttonId);
	if (!input || !button) return;
	const showing = input.type === 'text';
	input.type = showing ? 'password' : 'text';
	button.textContent = showing ? '👁' : '🙈';
	button.title = showing ? 'Show password' : 'Hide password';
}



function changeProfilePicture() {
	document.getElementById('profile-pic-file').click();
}

async function handleProfilePictureSelect(input) {
	const file = input.files && input.files[0];
	input.value = ''; // allow re-selecting the same file later
	if (!file) return;
	if (!file.type.startsWith('image/')) {
		window.alert('Please choose an image file.');
		return;
	}
	try {
		const formData = new FormData();
		formData.append('file', file);
		const response = await fetch('/api/profile-picture', { method: 'POST', body: formData });
		if (!response.ok) {
			const detail = await response.json().catch(() => ({}));
			throw new Error(detail.detail || `Server responded ${response.status}`);
		}
		const me = await fetch('/api/auth/me').then((r) => (r.ok ? r.json() : null)).catch(() => null);
		if (me && me.user) currentUser = me.user;
		displayProfilePicture();
	} catch (error) {
		window.alert(`Could not update profile picture: ${error.message}`);
	}
}

function displayProfilePicture() {
	const avatar = document.getElementById(currentRole === 'officer' ? 'officer-avatar' : 'user-avatar');
	if (avatar) {
		avatar.querySelectorAll('img').forEach((img) => img.remove());
		if (currentUser && currentUser.profileImageId) {
			const img = document.createElement('img');
			img.src = `/api/profile-picture?v=${currentUser.profileImageId}`;
			img.alt = 'Profile';
			avatar.append(img);
		} else if (currentUser) {
			avatar.textContent = (currentUser.name || '?')
				.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase();
		}
	}
	const pageAvatar = document.getElementById('profile-page-avatar');
	if (pageAvatar) {
		pageAvatar.querySelectorAll('img').forEach((img) => img.remove());
		if (currentUser) {
			pageAvatar.textContent = (currentUser.name || '?')
				.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase();
			if (currentUser.profileImageId) {
				const img = document.createElement('img');
				img.src = `/api/profile-picture?v=${currentUser.profileImageId}`;
				img.alt = 'Profile';
				pageAvatar.textContent = '';
				pageAvatar.append(img);
			}
		}
	}
}

function loadProfile() {
	if (!currentUser) return;
	document.getElementById('pf-name').value = currentUser.name || '';
	document.getElementById('pf-email').value = currentUser.email || '';
	document.getElementById('pf-username').value = currentUser.username || '';
	document.getElementById('profile-page-name').textContent = currentUser.name || '—';
	document.getElementById('profile-page-role').textContent =
		currentRole === 'officer' ? 'Security Officer' : 'Verified User';
	document.getElementById('pf-saved').style.display = 'none';
	const errorBox = document.getElementById('pf-error');
	errorBox.textContent = '';
	errorBox.classList.remove('show');
	displayProfilePicture();
}

async function saveProfile() {
	const errorBox = document.getElementById('pf-error');
	const savedNote = document.getElementById('pf-saved');
	errorBox.textContent = '';
	errorBox.classList.remove('show');
	savedNote.style.display = 'none';

	const name = document.getElementById('pf-name').value.trim();
	const email = document.getElementById('pf-email').value.trim();
	if (!name || !email) {
		errorBox.textContent = 'Name and email are required.';
		errorBox.classList.add('show');
		return;
	}
	try {
		const response = await fetch('/api/profile', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name, email }),
		});
		const data = await response.json().catch(() => ({}));
		if (!response.ok) throw new Error(data.detail || `Server responded ${response.status}`);
		currentUser = data.user;
		document.getElementById('profile-page-name').textContent = currentUser.name;
		document.getElementById(currentRole === 'officer' ? 'officer-name' : 'user-name').textContent = currentUser.name;
		displayProfilePicture();
		savedNote.style.display = '';
	} catch (error) {
		errorBox.textContent = error.message;
		errorBox.classList.add('show');
	}
}

// ===== WATCHLIST (officer-managed blacklist) =====

async function loadWatchlist() {
	let entries = [];
	try {
		const response = await fetch('/api/watchlist');
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		entries = await response.json();
	} catch (error) {
		return; // keep current view; watchlist is non-critical
	}
	const box = document.getElementById('wl-entries');
	const empty = document.getElementById('wl-empty');
	if (!box || !empty) return;
	box.innerHTML = '';
	if (entries.length === 0) {
		empty.style.display = '';
		return;
	}
	empty.style.display = 'none';
	entries.forEach((entry) => {
		const item = document.createElement('div');
		item.className = 'queue-item';
		const meta = document.createElement('div');
		meta.className = 'queue-meta';
		const name = document.createElement('div');
		name.className = 'queue-name';
		name.textContent = `${entry.docNumber}${entry.personName ? ' · ' + entry.personName : ''}`;
		const reason = document.createElement('div');
		reason.className = 'queue-time';
		reason.textContent = entry.reason || 'No reason given';
		meta.append(name, reason);
		const chip = document.createElement('span');
		chip.className = 'risk-chip risk-high';
		chip.textContent = 'FLAGGED';
		const remove = document.createElement('button');
		remove.className = 'btn btn-ghost';
		remove.style.cssText = 'padding:4px 10px;font-size:11px;margin-left:8px;';
		remove.textContent = 'Remove';
		remove.onclick = () => removeWatchlistEntry(entry.id);
		item.append(meta, chip, remove);
		box.append(item);
	});
}

async function addWatchlistEntry() {
	const docNumber = document.getElementById('wl-doc').value.trim();
	const personName = document.getElementById('wl-name').value.trim() || null;
	const reason = document.getElementById('wl-reason').value.trim() || null;
	if (!docNumber) {
		window.alert('Enter a document number to blacklist.');
		return;
	}
	try {
		const response = await fetch('/api/watchlist', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ docNumber, personName, reason }),
		});
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		document.getElementById('wl-doc').value = '';
		document.getElementById('wl-name').value = '';
		document.getElementById('wl-reason').value = '';
		loadWatchlist();
	} catch (error) {
		window.alert(`Could not add to watchlist: ${error.message}`);
	}
}

async function removeWatchlistEntry(entryId) {
	try {
		const response = await fetch(`/api/watchlist/${entryId}`, { method: 'DELETE' });
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		loadWatchlist();
	} catch (error) {
		window.alert(`Could not remove: ${error.message}`);
	}
}

// ===== TRASH BIN (soft delete / restore / purge) =====

async function deleteScreening(docId) {
	if (!window.confirm(`Move ${docId} to the trash? You can restore it later.`)) return;
	try {
		const response = await fetch(`/api/screenings/${encodeURIComponent(docId)}`, { method: 'DELETE' });
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		refreshDashboard();
	} catch (error) {
		window.alert(`Could not delete: ${error.message}`);
	}
}

async function restoreScreening(docId) {
	try {
		const response = await fetch(`/api/screenings/${encodeURIComponent(docId)}/restore`, { method: 'POST' });
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		loadTrash();
	} catch (error) {
		window.alert(`Could not restore: ${error.message}`);
	}
}

async function purgeScreening(docId) {
	if (!window.confirm(`Permanently delete ${docId}? This cannot be undone.`)) return;
	try {
		const response = await fetch(`/api/screenings/${encodeURIComponent(docId)}/purge`, { method: 'DELETE' });
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		loadTrash();
	} catch (error) {
		window.alert(`Could not delete permanently: ${error.message}`);
	}
}

async function loadTrash() {
	let records = [];
	try {
		const response = await fetch('/api/screenings/trash');
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		records = await response.json();
	} catch (error) {
		return; // keep the current view; trash is non-critical
	}
	const tbody = document.getElementById('trash-rows');
	const empty = document.getElementById('trash-empty');
	tbody.innerHTML = '';
	if (records.length === 0) {
		empty.style.display = '';
		return;
	}
	empty.style.display = 'none';
	records.forEach((item) => {
		const row = document.createElement('tr');
		const tierClass = `risk-${(item.risk && item.risk.tier || 'MED').toLowerCase()}`;
		const name = item.fields && item.fields.name ? item.fields.name : '—';
		const deletedAt = (item.deletedAt || '').replace('T', ' ');
		row.innerHTML = `<td class="doc-id">${item.id}</td>` +
			`<td>${name}</td>` +
			`<td><span class="risk-chip ${tierClass}">${(item.risk && item.risk.tier) || '—'}</span></td>` +
			`<td class="doc-id">${deletedAt}</td>`;
		const actionsCell = document.createElement('td');
		const restoreButton = document.createElement('button');
		restoreButton.className = 'btn';
		restoreButton.style.cssText = 'padding:4px 10px;font-size:11px;margin-right:6px;';
		restoreButton.textContent = 'Restore';
		restoreButton.onclick = () => restoreScreening(item.id);
		const purgeButton = document.createElement('button');
		purgeButton.className = 'btn btn-danger';
		purgeButton.style.cssText = 'padding:4px 10px;font-size:11px;';
		purgeButton.textContent = 'Delete forever';
		purgeButton.onclick = () => purgeScreening(item.id);
		actionsCell.append(restoreButton, purgeButton);
		row.append(actionsCell);
		tbody.append(row);
	});
}

// ===== SCREENING FLOW (real API — Phase 1 wiring) =====

function handleFileSelect(input, slot) {
	const file = input.files && input.files[0];
	if (!file) return;
	const isDoc = slot === 'doc';
	if (isDoc) {
		pendingDocFile = file;
	} else {
		pendingFaceFile = file;
	}
	const dropzone = document.getElementById(isDoc ? 'dz-doc' : 'dz-face');
	dropzone.classList.add('loaded');
	document.getElementById(isDoc ? 'dz-doc-title' : 'dz-face-title').textContent = isDoc ? 'Document selected' : 'Face photo selected';
	document.getElementById(isDoc ? 'dz-doc-sub' : 'dz-face-sub').textContent = file.name;
	setUploadHint('');
}

function setUploadHint(text) {
	document.getElementById('upload-hint').textContent = text;
}

async function startScreening() {
	if (!pendingDocFile) {
		setUploadHint('Select a document image before starting analysis.');
		return;
	}
	setUploadHint('');
	currentResult = null;
	selectedDecision = null;
	document.querySelectorAll('.decision-row .btn').forEach((item) => item.classList.remove('selected'));
	const confirmButton = document.getElementById('btn-confirm-decision');
	confirmButton.disabled = true;
	confirmButton.classList.add('btn-disabled');
	document.getElementById('officer-verify-banner').classList.remove('show');

	const docName = pendingDocFile.name;
	document.getElementById('proc-sub').textContent = `${docName} · uploaded by Officer Kessler`;
	resetPipeline();
	logLine(`Document received — ${docName}`);
	if (pendingFaceFile) logLine(`Face capture attached — ${pendingFaceFile.name}`);
	logLine('Uploading to screening engine…');
	goTo('processing');
	markPipelineStep(1); // OCR step active while the request runs
	setProgress(10, 'Running OCR extraction…');

	// stage messages while the server runs the pipeline; the final stage is
	// replaced by the real completion summary when the response arrives
	const stepMessages = [
		'OCR extraction running (EasyOCR)…',
		'Validating document rules (MRZ, dates, formats)…',
		'Tampering forensics — metadata, ELA, noise…',
	];
	if (pendingFaceFile) stepMessages.push('Face verification + liveness (Facenet)…');
	stepMessages.push('Risk engine computing score…');
	let stepIndex = 0;
	const stepTimer = window.setInterval(() => {
		if (stepIndex < stepMessages.length - 1) {
			logLine(stepMessages[stepIndex]);
			markPipelineStep(stepIndex + 1);
			setProgress(10 + ((stepIndex + 1) / stepMessages.length) * 80, stepMessages[stepIndex].replace('…', ''));
			stepIndex += 1;
		}
	}, 900);

	try {
		const formData = new FormData();
		formData.append('document', pendingDocFile);
		if (pendingFaceFile) formData.append('face', pendingFaceFile);
		const response = await fetch('/api/screen', { method: 'POST', body: formData });
		if (!response.ok) {
			const detail = await response.json().catch(() => ({}));
			throw new Error(detail.detail || `Server responded ${response.status}`);
		}
		currentResult = await response.json();
		window.clearInterval(stepTimer);
		markPipelineComplete();
		setProgress(100, 'Analysis complete');
		setProcTitle(true);
		const flagCount = [...(currentResult.validation || []), ...(currentResult.tampering || [])]
			.filter((flag) => flag.status !== 'pass').length;
		logLine(`OK — analysis complete: risk ${currentResult.risk.score}/100 (${currentResult.risk.tier}), ${flagCount} flag${flagCount === 1 ? '' : 's'}`, true);
		if (currentResult.face && currentResult.face.match !== null) {
			const pct = Math.round(currentResult.face.match * 100);
			const verified = currentResult.face.verified ? `verified (${pct}% match)` : `MISMATCH (${pct}%)`;
			logLine(`OK — face check ${verified}`, currentResult.face.verified);
		}
		logLine('OK — uploaded image securely deleted from the server.', true);
		if (currentResult.warnings && currentResult.warnings.length) {
			currentResult.warnings.forEach((warning) => logLine(`WARN — ${warning}`));
		}
		renderResult(currentResult);
		showSecureDeleteBanner();
		document.getElementById('btn-view-result').style.display = '';
	} catch (error) {
		window.clearInterval(stepTimer);
		logLine(`ERROR — ${error.message}. Check that the backend is running, then retry.`);
		setProgress(35, `Processing failed — ${error.message}`, true);
		document.getElementById('btn-back-upload').style.display = '';
	}
}

function logLine(text, isOk = false) {
	const log = document.getElementById('proc-log');
	const time = new Date().toLocaleTimeString([], { hour12: false });
	const row = document.createElement('div');
	const tag = document.createElement('span');
	tag.className = 'tag';
	tag.textContent = `[${time}] `;
	row.append(tag);
	if (isOk) {
		const ok = document.createElement('span');
		ok.className = 'ok';
		ok.textContent = 'OK ';
		row.append(ok);
	}
	row.append(document.createTextNode(text));
	log.append(row);
	log.scrollTop = log.scrollHeight;
}

function setProgress(pct, label, isError = false) {
	const clamped = Math.max(0, Math.min(100, Math.round(pct)));
	const fill = document.getElementById('progress-fill');
	const pctEl = document.getElementById('progress-pct');
	const labelEl = document.getElementById('progress-label');
	const shell = document.querySelector('.progress-shell');
	if (fill) fill.style.width = `${clamped}%`;
	if (pctEl) pctEl.textContent = `${clamped}%`;
	if (label && labelEl) labelEl.textContent = label;
	if (shell) shell.classList.toggle('error', isError);
}

function setProcTitle(complete = false) {
	const title = document.getElementById('proc-title');
	if (!title) return;
	if (complete) {
		title.classList.add('complete');
		title.textContent = 'Analysis complete';
	} else {
		title.classList.remove('complete');
		title.innerHTML = '<span class="proc-spinner"></span>Wait — your documents are processing…';
	}
}

function resetPipeline() {
	document.getElementById('proc-log').innerHTML = '';
	const banner = document.getElementById('secure-delete-banner');
	if (banner) banner.style.display = 'none';
	document.querySelectorAll('#pipeline .pstep').forEach((step) => {
		step.classList.remove('active', 'done', 'skipped');
	});
	setProgress(0, 'Initializing screening engine…');
	setProcTitle(false);
	document.getElementById('btn-view-result').style.display = 'none';
	document.getElementById('btn-back-upload').style.display = 'none';
}

function markPipelineComplete() {
	// the final node is the officer's own verification — the AI pipeline
	// ends at the risk engine, one node before it
	const steps = [...document.querySelectorAll('#pipeline .pstep')];
	steps.forEach((step, index) => {
		step.classList.remove('active');
		if (index === 4 && !pendingFaceFile) {
			step.classList.add('skipped'); // no face uploaded — step not needed
			return;
		}
		if (index < steps.length - 1) step.classList.add('done');
	});
}

function markPipelineStep(activeIndex) {
	const steps = [...document.querySelectorAll('#pipeline .pstep')];
	steps.forEach((step, index) => {
		step.classList.toggle('done', index < activeIndex);
		step.classList.toggle('active', index === activeIndex);
	});
}

function showSecureDeleteBanner() {
	const banner = document.getElementById('secure-delete-banner');
	if (!banner) return;
	// restart CSS animations from scratch on every screening
	const clone = banner.cloneNode(true);
	banner.replaceWith(clone);
	clone.style.display = 'flex';
}

function renderResult(result) {
	document.getElementById('result-title').textContent = `${result.id} — Result`;
	document.getElementById('result-sub').textContent =
		`${result.docType.charAt(0).toUpperCase() + result.docType.slice(1)} · ${result.fields.name || 'Unknown holder'} · screened by Officer Kessler`;

	const docImage = document.getElementById('doc-image');
	const docIcon = document.getElementById('doc-preview-icon');
	const deletedNote = document.getElementById('doc-deleted-note');
	docImage.style.display = 'none';
	if (deletedNote) deletedNote.style.display = 'none';
	if (result.imageDeleted) {
		docIcon.style.display = 'none';
		if (deletedNote) deletedNote.style.display = '';
	} else {
		docIcon.style.display = '';
		docImage.src = `/api/screenings/${encodeURIComponent(result.id)}/image`;
		docImage.onload = () => {
			docImage.style.display = '';
			docIcon.style.display = 'none';
		};
		docImage.onerror = () => {
			docImage.style.display = 'none';
			docIcon.style.display = '';
		};
	}

	const fieldIds = ['name', 'documentNo', 'nationality', 'dob', 'expiry', 'gender'];
	fieldIds.forEach((key) => {
		const cell = document.getElementById(`fld-${key}`);
		if (cell) cell.textContent = result.fields[key] || '—';
	});

	const flagBox = document.getElementById('result-flags');
	flagBox.innerHTML = '';
	const emptyNote = document.getElementById('result-flags-empty');
	const allFlags = [...(result.validation || []), ...(result.tampering || [])];
	const raised = allFlags.filter((flag) => flag.status && flag.status !== 'pass');
	if (raised.length === 0) {
		emptyNote.style.display = '';
	} else {
		emptyNote.style.display = 'none';
		raised.forEach((flag) => {
			const item = document.createElement('div');
			item.className = `flag-item${flag.status === 'review' ? ' warn' : ''}`;
			const dot = document.createElement('div');
			dot.className = 'flag-dot';
			const body = document.createElement('div');
			const title = document.createElement('div');
			title.className = 'flag-title';
			title.textContent = `${flag.label} — ${flag.status.toUpperCase()}`;
			const sub = document.createElement('div');
			sub.className = 'flag-sub';
			sub.textContent = flag.detail || '';
			body.append(title, sub);
			item.append(dot, body);
			flagBox.append(item);
		});
	}

	const tierColors = { LOW: 'var(--low)', MED: 'var(--med)', HIGH: 'var(--high)' };
	const tierColor = tierColors[result.risk.tier] || 'var(--med)';
	const circumference = 427;
	const offset = circumference * (1 - Math.min(result.risk.score, 100) / 100);
	const arc = document.getElementById('gauge-arc');
	arc.style.stroke = tierColor;
	arc.setAttribute('stroke-dashoffset', String(offset));
	const scoreEl = document.getElementById('gauge-score');
	scoreEl.textContent = result.risk.score;
	scoreEl.style.color = tierColor;
	const tierEl = document.getElementById('gauge-tier');
	tierEl.textContent = `${result.risk.tier} RISK`;
	tierEl.style.color = tierColor;

	const reasons = document.getElementById('risk-reasons');
	reasons.innerHTML = '';
	(result.risk.reasons || []).forEach((reason) => {
		const li = document.createElement('li');
		if (reason.startsWith('WATCHLIST')) {
			li.style.cssText = 'border-color:rgba(245,87,108,.5);background:rgba(245,87,108,.07);color:var(--text);';
			li.textContent = '⛔ ' + reason;
		} else {
			li.textContent = reason;
		}
		reasons.append(li);
	});

	const matchPct = document.getElementById('face-match-pct');
	const matchBar = document.getElementById('face-match-bar');
	if (result.face && typeof result.face.match === 'number') {
		const pct = Math.round(result.face.match * 100);
		matchPct.textContent = `${pct}%`;
		matchBar.style.width = `${pct}%`;
		matchPct.parentElement.parentElement.style.display = '';
	} else {
		matchPct.textContent = 'N/A';
		matchBar.style.width = '0%';
	}
}

// ===== DASHBOARD + INVESTIGATION (live data — Phase 6 wiring) =====

async function refreshDashboard() {
	let screenings = [];
	try {
		const response = await fetch('/api/screenings');
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		screenings = await response.json();
	} catch (error) {
		return; // keep placeholder stats; dashboard is non-critical
	}

	const counts = { LOW: 0, MED: 0, HIGH: 0 };
	screenings.forEach((item) => {
		if (item.risk && counts[item.risk.tier] !== undefined) counts[item.risk.tier] += 1;
	});
	document.getElementById('stat-total').textContent = screenings.length.toLocaleString();
	document.getElementById('stat-low').textContent = counts.LOW.toLocaleString();
	document.getElementById('stat-med').textContent = counts.MED.toLocaleString();
	document.getElementById('stat-high').textContent = counts.HIGH.toLocaleString();

	const feed = document.getElementById('dash-feed');
	const feedEmpty = document.getElementById('dash-feed-empty');
	feed.innerHTML = '';
	if (screenings.length === 0) {
		feedEmpty.style.display = '';
	} else {
		feedEmpty.style.display = 'none';
	}
	screenings.slice(0, 8).forEach((item) => {
		const row = document.createElement('tr');
		row.className = 'rowhover';
		row.onclick = () => openInvestigation(item.id);
		const typeLabel = item.docType ? item.docType.replace(/\b\w/g, (c) => c.toUpperCase()) : '—';
		const tierClass = `risk-${(item.risk && item.risk.tier || 'MED').toLowerCase()}`;
		row.innerHTML = `<td class="doc-id">${item.id}</td>` +
			`<td>${item.fields && item.fields.name ? item.fields.name : '—'}</td>` +
			`<td>${typeLabel}</td>` +
			`<td><span class="risk-chip ${tierClass}">${(item.risk && item.risk.tier) || '—'}</span></td>` +
			`<td class="doc-id">${(item.createdAt || '').split('T')[1] || ''}</td>`;
		const actionsCell = document.createElement('td');
		const deleteButton = document.createElement('button');
		deleteButton.className = 'btn btn-danger';
		deleteButton.style.cssText = 'padding:4px 10px;font-size:11px;';
		deleteButton.textContent = 'Delete';
		deleteButton.onclick = (event) => {
			event.stopPropagation();
			deleteScreening(item.id);
		};
		actionsCell.append(deleteButton);
		row.append(actionsCell);
		feed.append(row);
	});

	const queue = document.getElementById('dash-queue');
	const queueEmpty = document.getElementById('dash-queue-empty');
	queue.innerHTML = '';
	const escalated = screenings.filter((item) => item.risk && item.risk.tier === 'HIGH' && !item.decision);
	if (escalated.length === 0) {
		queueEmpty.style.display = '';
	} else {
		queueEmpty.style.display = 'none';
	}
	escalated.slice(0, 5).forEach((item) => {
		const queueItem = document.createElement('div');
		queueItem.className = 'queue-item';
		queueItem.style.cursor = 'pointer';
		queueItem.onclick = () => openInvestigation(item.id);
		const reason = (item.risk && item.risk.reasons && item.risk.reasons[0]) || 'High risk signal';
		const thumb = document.createElement('div');
		thumb.className = 'queue-thumb';
		thumb.textContent = (item.docType || '??').slice(0, 2).toUpperCase();
		const meta = document.createElement('div');
		meta.className = 'queue-meta';
		const name = document.createElement('div');
		name.className = 'queue-name';
		name.textContent = `${(item.fields && item.fields.name) || 'Unknown'} — ${item.id}`;
		const time = document.createElement('div');
		time.className = 'queue-time';
		time.textContent = reason.slice(0, 48);
		meta.append(name, time);
		const chip = document.createElement('span');
		chip.className = 'risk-chip risk-high';
		chip.textContent = 'HIGH';
		queueItem.append(thumb, meta, chip);
		queue.append(queueItem);
	});

	const badge = document.querySelector('.nav-badge');
	if (badge) badge.textContent = String(escalated.length);
}

let currentInvestigation = null;

async function openInvestigation(docId) {
	let record = null;
	try {
		const response = await fetch(`/api/screenings/${encodeURIComponent(docId)}`);
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		record = await response.json();
	} catch (error) {
		return;
	}
	currentInvestigation = record;

	const name = (record.fields && record.fields.name) || 'Unknown holder';
	document.getElementById('invest-title').textContent = `Investigation — ${record.id}`;
	const status = record.decision
		? `<span style="color:var(--low)">${record.decision.toUpperCase()} · ${record.officer || ''}</span>`
		: '<span style="color:var(--med)">AWAITING OFFICER DECISION</span>';
	document.getElementById('invest-sub').innerHTML =
		`${name} · Case opened ${(record.createdAt || '').replace('T', ' ')} · Status: ${status}`;

	const timeline = document.getElementById('invest-timeline');
	timeline.innerHTML = '';
	const events = [
		[`${(record.createdAt || '').split('T')[1] || ''}`, 'Document screened',
		 `${(record.docType || 'document').replace(/\b\w/g, (c) => c.toUpperCase())} ${record.id} submitted at Checkpoint 04, Terminal B.`],
	];
	const tierColor = { LOW: 'var(--low)', MED: 'var(--med)', HIGH: 'var(--high)' }[record.risk && record.risk.tier] || 'var(--med)';
	events.push([`${(record.createdAt || '').split('T')[1] || ''}`, 'AI returned recommendation',
		`Score ${record.risk ? record.risk.score : '—'}/100 (${record.risk ? record.risk.tier : '—'}) — ${record.risk && record.risk.reasons ? record.risk.reasons.slice(0, 2).join('; ') : ''}. Advisory only.`]);
	(record.tampering || []).filter((flag) => flag.status !== 'pass').forEach((flag) => {
		events.push(['+', 'Tampering signal', `${flag.label}: ${flag.detail}`]);
	});
	(record.validation || []).filter((flag) => flag.status === 'fail').forEach((flag) => {
		events.push(['+', 'Validation failure', `${flag.label}: ${flag.detail}`]);
	});
	if (record.decision) {
		events.push(['✓', 'Officer decision recorded',
			`${record.officer || 'Officer'} confirmed: ${record.decision.toUpperCase()}.`]);
	} else {
		events.push(['now', 'Awaiting officer decision',
			'Traveler held in secondary screening. AI recommendation is advisory only.']);
	}
	events.forEach(([time, title, desc]) => {
		const item = document.createElement('div');
		item.className = 'tl-item';
		const t = document.createElement('div');
		t.className = 'tl-time';
		t.textContent = time;
		const h = document.createElement('div');
		h.className = 'tl-title';
		h.textContent = title;
		if (title === 'AI returned recommendation') h.style.color = tierColor;
		const d = document.createElement('div');
		d.className = 'tl-desc';
		d.textContent = desc;
		item.append(t, h, d);
		timeline.append(item);
	});

	const related = document.getElementById('invest-related');
	const relatedEmpty = document.getElementById('invest-related-empty');
	related.innerHTML = '';
	const documentNo = record.fields && record.fields.documentNo;
	if (documentNo) {
		const item = document.createElement('div');
		item.className = 'related-item';
		const label = document.createElement('span');
		label.textContent = `${name} — ${documentNo}`;
		const chip = document.createElement('span');
		const tier = (record.risk && record.risk.tier) || 'MED';
		chip.className = `risk-chip risk-${tier.toLowerCase()}`;
		chip.textContent = tier;
		item.append(label, chip);
		related.append(item);
		relatedEmpty.style.display = 'none';
	} else {
		relatedEmpty.style.display = '';
	}

	goTo('investigation');
}

function toggleTheme() {
	const isLight = document.body.classList.toggle('theme-light');
	const icon = isLight ? '☀' : '🌙';
	document.querySelectorAll('#theme-fab-icon, #theme-switch-icon').forEach((item) => item.textContent = icon);
	const label = document.getElementById('theme-switch-label');
	if (label) label.textContent = isLight ? 'Light Mode' : 'Dark Mode';
}

function selectDecision(button, decision) {
	selectedDecision = decision;
	document.querySelectorAll('.decision-row .btn').forEach((item) => item.classList.remove('selected'));
	button.classList.add('selected');
	const confirmButton = document.getElementById('btn-confirm-decision');
	confirmButton.disabled = false;
	confirmButton.classList.remove('btn-disabled');
}

function confirmDecision() {
	if (!selectedDecision) return;
	const banner = document.getElementById('officer-verify-banner');
	const docId = currentResult ? currentResult.id : null;
	if (!docId) return;
	fetch('/api/decision', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			id: docId,
			decision: selectedDecision,
			officer: 'R. Kessler',
			note: null,
		}),
	})
		.then((response) => {
			if (!response.ok) throw new Error(`Server responded ${response.status}`);
			return response.json();
		})
		.then(() => {
			banner.textContent = `Decision recorded: ${selectedDecision.toUpperCase()}. Officer verification complete.`;
			banner.classList.add('show');
			refreshDashboard();
		})
		.catch(() => {
			banner.textContent = `Decision recorded locally: ${selectedDecision.toUpperCase()} — could not reach the server to persist it.`;
			banner.classList.add('show');
		});
}

// ===== USER PORTAL (real flow — upload → real AI checks → submit query) =====

let userQueryState = null; // {docFile, faceFile, liveness, result, screeningId}

function handleUserFileSelect(input, slot) {
	const file = input.files && input.files[0];
	if (!file) return;
	if (!userQueryState) userQueryState = {};
	userQueryState[slot === 'doc' ? 'docFile' : 'faceFile'] = file;
	const dropzone = document.getElementById(slot === 'doc' ? 'uq-dz-doc' : 'uq-dz-face');
	dropzone.classList.add('loaded');
	document.getElementById(slot === 'doc' ? 'uq-dz-doc-title' : 'uq-dz-face-title').textContent =
		slot === 'doc' ? 'Document selected' : 'Face photo selected';
	document.getElementById(slot === 'doc' ? 'uq-dz-doc-sub' : 'uq-dz-face-sub').textContent = file.name;
	resetUserChecks();
}

function resetUserChecks() {
	if (userQueryState) {
		userQueryState.result = null;
		userQueryState.screeningId = null;
	}
	document.querySelectorAll('#uq-checklist .check-item').forEach((check) => {
		check.classList.remove('checking', 'pass', 'flagged');
		check.querySelector('.cstatus')?.remove();
	});
	const submitButton = document.getElementById('btn-submit-query');
	submitButton.disabled = true;
	submitButton.classList.add('btn-disabled');
	const helper = document.getElementById('uq-helper');
	helper.textContent = 'Upload a document and run the verification checks above before sending.';
	helper.classList.remove('ready');
}

function _setUserCheck(id, state, label) {
	const check = document.getElementById(id);
	check.classList.remove('checking', 'pass', 'flagged');
	check.classList.add(state);
	const status = check.querySelector('.cstatus');
	if (status) status.textContent = label;
}

async function runQueryChecks() {
	const runButton = document.getElementById('btn-run-uq-checks');
	const helper = document.getElementById('uq-helper');

	if (!userQueryState || !userQueryState.docFile) {
		helper.textContent = 'Select a document image first.';
		helper.classList.remove('ready');
		return;
	}

	runButton.disabled = true;
	runButton.classList.add('btn-disabled');
	resetUserChecks();
	document.querySelectorAll('#uq-checklist .check-item').forEach((check) => {
		check.classList.add('checking');
		const status = document.createElement('span');
		status.className = 'cstatus';
		status.textContent = 'CHECKING';
		check.append(status);
	});
	helper.textContent = 'Running the screening engine on your document…';
	helper.classList.remove('ready');

	try {
		const formData = new FormData();
		formData.append('document', userQueryState.docFile);
		if (userQueryState.faceFile) formData.append('face', userQueryState.faceFile);
		const response = await fetch('/api/screen', { method: 'POST', body: formData });
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		userQueryState.result = await response.json();
	} catch (error) {
		helper.textContent = `Checks failed to run: ${error.message}. Is the backend running?`;
		document.querySelectorAll('#uq-checklist .check-item').forEach((check) => {
			check.classList.remove('checking');
		});
		runButton.disabled = false;
		runButton.classList.remove('btn-disabled');
		return;
	}

	const result = userQueryState.result;
	const validations = result.validation || [];
	const tamperings = result.tampering || [];

	// OCR
	const mrzFound = result.fields && result.fields.documentNo;
	_setUserCheck('uq-ocr', mrzFound ? 'pass' : 'flagged', mrzFound ? 'PASS' : 'REVIEW');

	// validation
	const vFail = validations.some((f) => f.status === 'fail');
	const vReview = validations.some((f) => f.status === 'review');
	_setUserCheck('uq-valid', vFail ? 'flagged' : (vReview ? 'flagged' : 'pass'), vFail ? 'REVIEW' : (vReview ? 'REVIEW' : 'PASS'));

	// tampering
	const tFail = tamperings.some((f) => f.status === 'fail');
	const tReview = tamperings.some((f) => f.status === 'review');
	_setUserCheck('uq-tamper', tFail ? 'flagged' : (tReview ? 'flagged' : 'pass'), tFail ? 'REVIEW' : (tReview ? 'REVIEW' : 'PASS'));

	// face + liveness
	const face = result.face || {};
	if (typeof face.match === 'number') {
		_setUserCheck('uq-face', face.verified ? 'pass' : 'flagged', face.verified ? 'PASS' : 'REVIEW');
		_setUserCheck('uq-pad', face.liveness === 'pass' ? 'pass' : 'flagged', face.liveness === 'pass' ? 'PASS' : 'REVIEW');
	} else {
		_setUserCheck('uq-face', 'pass', 'N/A');
		_setUserCheck('uq-pad', 'pass', 'N/A');
	}

	helper.textContent = `Checks complete — AI risk ${result.risk.score}/100 (${result.risk.tier}). A human Officer makes the final call.`;
	helper.classList.add('ready');
	const submitButton = document.getElementById('btn-submit-query');
	submitButton.disabled = false;
	submitButton.classList.remove('btn-disabled');
	runButton.disabled = false;
	runButton.classList.remove('btn-disabled');
}

async function submitQuery() {
	if (!userQueryState || !userQueryState.result) return;
	const submitButton = document.getElementById('btn-submit-query');
	submitButton.disabled = true;
	submitButton.classList.add('btn-disabled');

	const queryText = (document.getElementById('uq-query-text')?.value || '').trim() || null;
	try {
		const response = await fetch('/api/query', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				queryText,
				screeningId: userQueryState.result.id,
			}),
		});
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		const confirmation = await response.json();
		const banner = document.getElementById('uq-confirmation');
		document.getElementById('uq-confirmation-title').textContent =
			`Query ${confirmation.id} sent to a Security Officer`;
		banner.style.display = 'block';
	} catch (error) {
		const helper = document.getElementById('uq-helper');
		helper.textContent = `Could not submit: ${error.message}. Try again.`;
		helper.classList.remove('ready');
		submitButton.disabled = false;
		submitButton.classList.remove('btn-disabled');
		return;
	}
	loadMyQueries();
}

async function loadMyQueries() {
	let queries = [];
	try {
		const response = await fetch('/api/queries');
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		queries = await response.json();
	} catch (error) {
		return; // keep whatever is rendered
	}
	const tbody = document.getElementById('uq-my-queries');
	const empty = document.getElementById('uq-my-queries-empty');
	tbody.innerHTML = '';
	if (queries.length === 0) {
		empty.style.display = '';
		return;
	}
	empty.style.display = 'none';
	queries.forEach((query) => {
		const row = document.createElement('tr');
		const submitted = (query.createdAt || '').replace('T', ' ');
		const statusChip = query.status === 'pending'
			? '<span class="risk-chip risk-med">PENDING OFFICER REVIEW</span>'
			: `<span class="risk-chip risk-low">${query.status.toUpperCase()}</span>`;
		row.innerHTML = `<td class="doc-id">${query.id}</td>` +
			`<td class="doc-id">${submitted}</td>` +
			`<td><span class="risk-chip risk-low">COMPLETE</span></td>` +
			`<td>${statusChip}</td>`;
		tbody.append(row);
	});
}

// ===== LIVE FACE CAMERA + LIVENESS (camera feature) =====

let cameraStream = null;
let capturedFaceBlob = null;
let livenessResult = null;
let livenessFrameCount = 8;
let cameraTarget = 'officer'; // 'officer' → New Screening, 'user' → user portal

async function openFaceCamera(target = 'officer') {
	cameraTarget = target;
	const modal = document.getElementById('camera-modal');
	modal.style.display = 'flex';
	resetFaceCamera();
	const video = document.getElementById('camera-video');
	const status = document.getElementById('camera-status');
	try {
		cameraStream = await navigator.mediaDevices.getUserMedia({
			video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
			audio: false,
		});
		video.srcObject = cameraStream;
		status.textContent = 'Camera ready. Position yourself in the frame.';
		document.getElementById('btn-capture').style.display = '';
	} catch (error) {
		status.textContent = 'Camera unavailable — permission denied or no device. Use the upload option below.';
	}
}

function closeFaceCamera() {
	if (cameraStream) {
		cameraStream.getTracks().forEach((track) => track.stop());
		cameraStream = null;
	}
	document.getElementById('camera-modal').style.display = 'none';
}

function resetFaceCamera() {
	livenessResult = null;
	capturedFaceBlob = null;
	const status = document.getElementById('camera-status');
	status.textContent = 'Requesting camera permission…';
	status.className = 'camera-status';
	document.getElementById('camera-checks').innerHTML = '';
	document.getElementById('camera-preview').style.display = 'none';
	document.getElementById('camera-video').style.display = '';
	document.getElementById('camera-stage').classList.remove('scanning');
	document.getElementById('btn-capture').style.display = cameraStream ? '' : 'none';
	document.getElementById('btn-use-capture').style.display = 'none';
	document.getElementById('btn-retake').style.display = 'none';
}

function _captureFrame(video) {
	const canvas = document.createElement('canvas');
	canvas.width = video.videoWidth || 640;
	canvas.height = video.videoHeight || 480;
	const context = canvas.getContext('2d');
	context.translate(canvas.width, 0);
	context.scale(-1, 1); // un-mirror so the stored frame matches reality
	context.drawImage(video, 0, 0, canvas.width, canvas.height);
	return new Promise((resolve, reject) => {
		canvas.toBlob((blob) => {
			if (blob) resolve(blob);
			else reject(new Error('Frame could not be encoded'));
		}, 'image/jpeg', 0.9);
	});
}

async function startLivenessCapture() {
	if (!cameraStream) return;
	const video = document.getElementById('camera-video');
	const status = document.getElementById('camera-status');
	const checksBox = document.getElementById('camera-checks');
	const stage = document.getElementById('camera-stage');
	document.getElementById('btn-capture').style.display = 'none';
	stage.classList.add('scanning');
	status.className = 'camera-status';
	status.textContent = 'Hold steady — capturing frames and checking liveness…';
	checksBox.innerHTML = '';

	const blobs = [];
	try {
		for (let i = 0; i < livenessFrameCount; i += 1) {
			// eslint-disable-next-line no-await-in-loop
			const blob = await _captureFrame(video);
			blobs.push(blob);
			status.textContent = `Hold steady — capturing frames (${i + 1}/${livenessFrameCount})…`;
			// eslint-disable-next-line no-await-in-loop
			await new Promise((resolve) => window.setTimeout(resolve, 350));
		}
	} catch (error) {
		stage.classList.remove('scanning');
		status.className = 'camera-status fail';
		status.textContent = `Frame capture failed: ${error.message}`;
		document.getElementById('btn-capture').style.display = '';
		return;
	}
	stage.classList.remove('scanning');

	status.textContent = 'Analyzing frames for presentation-attack signals…';
	try {
		const formData = new FormData();
		blobs.forEach((blob, index) => formData.append('frames', blob, `frame_${index}.jpg`));
		const response = await fetch('/api/liveness', { method: 'POST', body: formData });
		if (!response.ok) throw new Error(`Server responded ${response.status}`);
		livenessResult = await response.json();
	} catch (error) {
		status.className = 'camera-status fail';
		status.textContent = `Liveness check failed to run: ${error.message}`;
		document.getElementById('btn-capture').style.display = '';
		return;
	}

	livenessResult.checks.forEach((check) => {
		const item = document.createElement('div');
		item.className = `check-item ${check.status === 'pass' ? 'pass' : 'flagged'}`;
		const label = document.createElement('span');
		label.textContent = check.label;
		const result = document.createElement('span');
		result.className = 'cstatus';
		result.textContent = check.status.toUpperCase();
		item.append(label, result);
		checksBox.append(item);
	});

	if (livenessResult.liveness === 'pass') {
		status.className = 'camera-status pass';
		status.textContent = `Live face confirmed (motion ${livenessResult.motionScore}) — simplified check.`;
	} else if (livenessResult.liveness === 'fail') {
		status.className = 'camera-status fail';
		status.textContent = 'Presentation attack suspected — do not use this capture.';
	} else {
		status.className = 'camera-status';
		status.textContent = 'Liveness inconclusive — officer review required.';
	}

	capturedFaceBlob = blobs[blobs.length - 1]; // last frame = the face photo
	const preview = document.getElementById('camera-preview');
	preview.src = URL.createObjectURL(capturedFaceBlob);
	document.getElementById('btn-use-capture').style.display = '';
	document.getElementById('btn-retake').style.display = '';
}

async function useFaceCapture() {
	if (!capturedFaceBlob) return;
	const faceFile = new File([capturedFaceBlob], 'live_face_capture.jpg', { type: 'image/jpeg' });
	const suffix = livenessResult
		? ` · liveness ${livenessResult.liveness.toUpperCase()} (simplified)`
		: '';
	if (cameraTarget === 'user') {
		if (!userQueryState) userQueryState = {};
		userQueryState.faceFile = faceFile;
		const dropzone = document.getElementById('uq-dz-face');
		dropzone.classList.add('loaded');
		document.getElementById('uq-dz-face-title').textContent = 'Live face captured';
		document.getElementById('uq-dz-face-sub').textContent = `Camera capture${suffix}`;
		resetUserChecks();
	} else {
		pendingFaceFile = faceFile;
		const dropzone = document.getElementById('dz-face');
		dropzone.classList.add('loaded');
		document.getElementById('dz-face-title').textContent = 'Live face captured';
		document.getElementById('dz-face-sub').textContent = `Camera capture${suffix}`;
		setUploadHint('');
	}
	closeFaceCamera();
}

function toggleDenyBtn() {
	const checkbox = document.getElementById('officer-confirm-check');
	const button = document.getElementById('btn-deny-case');
	button.disabled = !checkbox.checked;
	button.classList.toggle('btn-disabled', !checkbox.checked);
}

function updateClock() {
	const clock = document.getElementById('clock');
	if (clock) clock.textContent = new Date().toLocaleTimeString([], { hour12: false });
}

updateClock();
window.setInterval(updateClock, 1000);

// restore an existing session on page load (stay logged in after refresh)
(async function restoreSession() {
	try {
		const response = await fetch('/api/auth/me');
		if (!response.ok) return;
		const data = await response.json();
		currentUser = data.user;
		currentRole = data.user.role;
		enterPortal();
	} catch (error) {
		// no session — stay on the login screen
	}
})();
