(function () {
  'use strict';
  var grid = document.getElementById('votes-grid');
  var status = document.getElementById('status');
  if (!grid) { return; }

  grid.addEventListener('click', function (event) {
    var button = event.target.closest('[data-vote]');
    if (!button) { return; }
    var card = button.closest('.restaurant');
    var id = card.getAttribute('data-id');
    var name = card.querySelector('h2').textContent;
    button.disabled = true;
    fetch(grid.getAttribute('data-vote-url').replace('__ID__', encodeURIComponent(id)), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRF-Token': grid.getAttribute('data-csrf') }
    }).then(function (response) {
      if (response.status === 401) { window.location.href = '/votes/login'; return null; }
      if (!response.ok) { throw new Error('HTTP ' + response.status); }
      return response.json();
    }).then(function (data) {
      if (!data) { return; }
      card.querySelector('[data-count]').textContent = data.votes;
      status.textContent = 'Thanks! ' + name + ' now has ' + data.votes + ' votes.';
    }).catch(function () {
      status.textContent = 'Could not register your vote for ' + name + '. Please try again.';
    }).then(function () {
      button.disabled = false;
    });
  });
})();
