document.addEventListener('DOMContentLoaded', () => {
    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('search-input');
    const profileContainer = document.getElementById('profile-container');
    const errorMessage = document.getElementById('error-message');

    const params = new URLSearchParams(window.location.search);
    const userId = params.get('id') || 'torvalds';

    if (userId) {
        fetchGitHubUser(userId);
    }

    searchForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const username = searchInput.value.trim();
        if (username) {
            window.history.pushState({}, '', `?id=${username}`);
            fetchGitHubUser(username);
        }
    });

    async function fetchGitHubUser(username) {
        profileContainer.classList.add('hidden');
        errorMessage.classList.add('hidden');

        try {
            const [userResponse, activityResponse] = await Promise.all([
                fetch(`https://api.github.com/users/${username}`),
                fetch(`https://api.github.com/users/${username}/events`)
            ]);

            if (!userResponse.ok) {
                throw new Error('User not found');
            }

            const userData = await userResponse.json();
            const activityData = await activityResponse.json();

            renderProfile(userData);
            renderActivity(activityData);

            profileContainer.classList.remove('hidden');
        } catch (error) {
            errorMessage.classList.remove('hidden');
        }
    }

    function renderProfile(data) {
        document.getElementById('avatar').src = data.avatar_url;
        document.getElementById('name').textContent = data.name || 'N/A';
        document.getElementById('login').textContent = `@${data.login}`;
        document.getElementById('bio').textContent = data.bio || '';
        document.getElementById('followers').textContent = data.followers;
        document.getElementById('following').textContent = data.following;
        document.getElementById('public_repos').textContent = data.public_repos;
    }

    function renderActivity(data) {
        const activityList = document.getElementById('activity-list');
        activityList.innerHTML = '';

        data.slice(0, 10).forEach(event => {
            const listItem = document.createElement('li');
            let actionText = '';

            switch (event.type) {
                case 'PushEvent':
                    actionText = `pushed to ${event.repo.name}`;
                    break;
                case 'CreateEvent':
                    actionText = `created a repository ${event.repo.name}`;
                    break;
                case 'WatchEvent':
                    actionText = `starred ${event.repo.name}`;
                    break;
                case 'PullRequestEvent':
                    actionText = `${event.payload.action} a pull request in ${event.repo.name}`;
                    break;
                default:
                    actionText = `${event.type.replace('Event', '')} in ${event.repo.name}`;
            }

            listItem.textContent = `${new Date(event.created_at).toLocaleDateString()}: You ${actionText}`;
            activityList.appendChild(listItem);
        });
    }
});