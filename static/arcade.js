// Update the tapped section in place instead of reloading the page and jumping back to the top.
// Without this script every control still works as a plain GET form or link.
(function () {
  "use strict";

  function regionOf(node) {
    return node.closest("[data-region]");
  }

  function sameRegion(name) {
    return document.querySelector('[data-region="' + name + '"]');
  }

  var FOCUSABLE = "button, a[href], input, select, textarea";

  function collapse(text) {
    return text.replace(/\s+/g, " ").trim();
  }

  // Find the control that had focus again after its region was replaced.
  // `index` is its position among the old region's focusable controls, taken before the swap.
  function focusMatch(region, focused, index) {
    if (!focused) return null;
    if (region.getAttribute("data-region") === "planet-quiz" &&
        focused.tagName === "BUTTON" && focused.name === "choice") {
      var result = region.querySelector('.quiz-answer[role="status"]');
      var next = result && region.querySelector("a.quiz-next[href]");
      if (next) {
        // A newly inserted status can be missed when focus moves immediately.
        next.setAttribute("aria-description", result.textContent.replace(/\s+/g, " ").trim());
        next.addEventListener("blur", function () {
          // Restore the server markup so unrelated updates do not replace this result again.
          next.removeAttribute("aria-description");
        }, { once: true });
        return next;
      }
    }
    if (focused.id) return region.querySelector("#" + CSS.escape(focused.id));
    var tag = focused.tagName.toLowerCase();
    if (focused.name) {
      var selector = tag + '[name="' + CSS.escape(focused.name) + '"]';
      var match = region.querySelector(selector + '[value="' + CSS.escape(focused.value) + '"]');
      return match || region.querySelector(selector);
    }
    // No id or name (e.g. the duel's Compare button): same tag and text, else the same position.
    var text = collapse(focused.textContent);
    var same = Array.prototype.find.call(region.querySelectorAll(tag), function (node) {
      return collapse(node.textContent) === text;
    });
    return same || (index >= 0 && region.querySelectorAll(FOCUSABLE)[index]) || null;
  }

  // Copy the section's result into the page's one persistent status, so screen readers announce it.
  function announce(region) {
    var status = document.querySelector("#arcade-status");
    if (!status) return;
    var result = region.querySelector(".duel-ratio, .birthday-results");
    var text = "";
    if (result && result.matches("ul")) {
      var label = result.getAttribute("aria-label");
      text = (label ? label + ": " : "") + Array.prototype.map.call(result.querySelectorAll("li"), function (item) {
        return collapse(item.textContent);
      }).join(", ");
    } else if (result) {
      text = collapse(result.textContent);
    }
    // Clear first so an identical result is announced again.
    status.textContent = "";
    status.textContent = text;
  }

  // Only the latest tap or back/forward may change the page; slower earlier responses are dropped.
  var latest = 0;

  async function update(url, origin, push) {
    var ticket = ++latest;
    var name = origin.getAttribute("data-region");
    var focused = origin.contains(document.activeElement) ? document.activeElement : null;
    var doc;
    try {
      var response = await fetch(url, { headers: { Accept: "text/html" } });
      doc = new DOMParser().parseFromString(await response.text(), "text/html");
    } catch (error) {
      if (ticket === latest) window.location.assign(url);
      return;
    }
    if (ticket !== latest) return;
    // The old region is detached after the swap, so note the control's position now.
    var index = -1;
    if (focused && !focused.id && !focused.name) {
      index = Array.prototype.indexOf.call(origin.querySelectorAll(FOCUSABLE), focused);
    }
    if (!doc.querySelector('[data-region="' + name + '"]')) {
      window.location.assign(url);
      return;
    }
    // Measure right before swapping, so scrolling done while the response loaded is kept.
    var before = sameRegion(name).getBoundingClientRect().top;
    doc.querySelectorAll("[data-region]").forEach(function (fresh) {
      var old = sameRegion(fresh.getAttribute("data-region"));
      if (old && old.outerHTML !== fresh.outerHTML) old.replaceWith(document.adoptNode(fresh));
    });
    // Keep the page's hash (e.g. #duel-title from the section nav) so back/forward and reloads stay on this section.
    if (push) {
      var pushed = new URL(url);
      if (window.location.hash) pushed.hash = window.location.hash;
      history.pushState(null, "", pushed.href);
    }
    // Undo only the shift the swap caused, so the tapped section stays put even if sections above changed height.
    var current = sameRegion(name);
    window.scrollBy(0, current.getBoundingClientRect().top - before);
    announce(current);
    if (focused && !document.contains(focused)) {
      var target = focusMatch(current, focused, index);
      if (target) target.focus({ preventScroll: true });
    }
  }

  function homeUrl(href) {
    var url = new URL(href, window.location.href);
    return url.origin === window.location.origin && url.pathname === "/" ? url : null;
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    var origin = regionOf(form);
    var url = homeUrl(form.action);
    if (!origin || !url || form.method.toLowerCase() !== "get") return;
    event.preventDefault();
    var data = new FormData(form);
    var submitter = event.submitter;
    if (submitter && submitter.name) data.append(submitter.name, submitter.value);
    // Start from the page's current query so other sections keep their state, then overwrite this form's fields.
    var params = new URL(window.location.href).searchParams;
    Array.prototype.forEach.call(form.elements || [], function (field) {
      if (field.name) params.delete(field.name);
    });
    var pairs = Array.from(data);
    pairs.forEach(function (pair) {
      params.delete(pair[0]);
    });
    pairs.forEach(function (pair) {
      params.append(pair[0], pair[1]);
    });
    url.search = params.toString();
    update(url.href, origin, true);
  });

  // Tapping a duel planet compares right away; the Compare button stays for pages without this script.
  document.addEventListener("change", function (event) {
    var radio = event.target;
    var form = radio.type === "radio" && radio.closest(".duel-form");
    if (form && form.requestSubmit) form.requestSubmit();
  });

  // Bar graph view hides the rocky inset, so a jump to it switches the chart back to circles first.
  function revealJumpTarget(hash) {
    var target = hash.length > 1 && document.getElementById(decodeURIComponent(hash.slice(1)));
    var bars = document.getElementById("scale-view-bars");
    var circles = document.getElementById("scale-view-circles");
    if (!target || !bars || !bars.checked || !circles || !target.closest(".rocky-inset")) return null;
    circles.checked = true;
    return target;
  }

  window.addEventListener("hashchange", function () {
    var target = revealJumpTarget(window.location.hash);
    if (target) target.scrollIntoView();
  });

  document.addEventListener("click", function (event) {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    var link = event.target.closest("a[href]");
    if (link && link.hash && link.pathname === window.location.pathname) revealJumpTarget(link.hash);
    var origin = link && regionOf(link);
    var url = link && homeUrl(link.href);
    if (!origin || !url || link.target) return;
    event.preventDefault();
    update(url.href, origin, true);
  });

  // Back and forward: refresh the sections for that URL around whichever section is on screen.
  window.addEventListener("popstate", function () {
    var regions = Array.prototype.slice.call(document.querySelectorAll("[data-region]"));
    var origin = regions.find(function (region) {
      return region.getBoundingClientRect().bottom > 0;
    }) || regions[0];
    if (origin) update(window.location.href, origin, false);
  });
})();
