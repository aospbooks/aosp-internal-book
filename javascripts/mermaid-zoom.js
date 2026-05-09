// Mermaid diagram click-to-zoom with high-quality (vector re-render) zoom
// and drag-to-pan. Works with Material theme's native mermaid rendering
// (open shadow DOM, patched from closed via overrides/main.html).
//
// Zoom is implemented by mutating the SVG's intrinsic style.width / style.height
// rather than CSS `transform: scale(...)`, so the browser repaints the vector
// at the new resolution at every zoom step. Centering uses overflow:auto on a
// flex-centering wrapper, so the diagram is centered when shown and zoom-to-
// center keeps the viewport-center content point stationary as scale changes.
;(function () {
  var overlay = document.createElement('div')
  overlay.id = 'mermaid-zoom-overlay'
  overlay.innerHTML =
    '<div class="mermaid-zoom-toolbar">' +
      '<button id="mzm-in" title="Zoom in (+)">+</button>' +
      '<span id="mzm-level">100%</span>' +
      '<button id="mzm-out" title="Zoom out (-)">−</button>' +
      '<button id="mzm-reset" title="Reset (0)">↺</button>' +
      '<button id="mzm-close" title="Close (Esc)">✕</button>' +
    '</div>' +
    '<div id="mzm-box">' +
      '<div id="mzm-wrap"></div>' +
    '</div>'
  document.body.appendChild(overlay)

  var box = document.getElementById('mzm-box')
  var wrap = document.getElementById('mzm-wrap')
  var lvl = document.getElementById('mzm-level')

  var s = 1
  var fitScale = 1
  var baseW = 0, baseH = 0
  var svgEl = null
  var MIN = 0.2, MAX = 8

  var drag = false
  var dragStartX = 0, dragStartY = 0
  var dragStartScrollX = 0, dragStartScrollY = 0

  function applyZoom () {
    if (!svgEl || !baseW) return
    svgEl.style.width = (baseW * s) + 'px'
    svgEl.style.height = (baseH * s) + 'px'
    lvl.textContent = Math.round(s * 100) + '%'
  }

  // Largest scale that fits the SVG inside the box with a small margin, clamped
  // to [MIN, MAX]. Used for fit-on-open and the reset button so wide LR
  // diagrams (column-clamped to ~700px on the page) fill the viewport instead
  // of opening at column width inside a full-width overlay.
  function computeFit () {
    if (!baseW || !baseH) return 1
    var availW = box.clientWidth - 48
    var availH = box.clientHeight - 48
    if (availW <= 0 || availH <= 0) return 1
    var fit = Math.min(availW / baseW, availH / baseH)
    return Math.max(MIN, Math.min(MAX, fit))
  }

  // Scroll the box so the wrapper's content is centered. No-op when content
  // fits the viewport (scrollWidth === clientWidth), which is the case at
  // scale 1 because flex centering already handles it.
  function recenter () {
    box.scrollLeft = Math.max(0, (box.scrollWidth - box.clientWidth) / 2)
    box.scrollTop = Math.max(0, (box.scrollHeight - box.clientHeight) / 2)
  }

  // Zoom toward the viewport center: keep the content point currently under
  // the viewport center stationary as the scale changes.
  function zoomTo (newS) {
    newS = Math.max(MIN, Math.min(MAX, newS))
    if (!svgEl || !baseW) { s = newS; applyZoom(); return }
    if (newS === s) return

    var boxRect = box.getBoundingClientRect()
    var vCenterX = boxRect.left + box.clientWidth / 2
    var vCenterY = boxRect.top + box.clientHeight / 2

    var before = svgEl.getBoundingClientRect()
    // Fraction of the SVG that's currently at viewport center. Can fall
    // outside [0, 1] when the user has panned past the SVG; that's fine.
    var fx = before.width ? (vCenterX - before.left) / before.width : 0.5
    var fy = before.height ? (vCenterY - before.top) / before.height : 0.5

    s = newS
    applyZoom()

    // Force layout, then read the new SVG position and adjust scroll so the
    // same fractional point sits at the viewport center.
    var after = svgEl.getBoundingClientRect()
    var newPointX = after.left + fx * after.width
    var newPointY = after.top + fy * after.height

    box.scrollLeft += (newPointX - vCenterX)
    box.scrollTop += (newPointY - vCenterY)
  }

  function findSvg (el) {
    if (el.shadowRoot) {
      var svg = el.shadowRoot.querySelector('svg')
      if (svg) return svg
    }
    return el.querySelector('svg')
  }

  function show (el) {
    var svg = findSvg(el)
    if (!svg) return

    var c = svg.cloneNode(true)

    // Give the clone a unique id so its scoped #mermaid-N CSS rules still
    // resolve after we reparent it.
    var origId = c.getAttribute('id') || ''
    var newId = origId + '-zoom'
    c.setAttribute('id', newId)
    var styleEl = c.querySelector('style')
    if (styleEl && origId) {
      styleEl.textContent = styleEl.textContent.split(origId).join(newId)
    }

    // Ensure a viewBox exists so style.width/height resize the rendering
    // instead of squashing it.
    if (!c.getAttribute('viewBox') && svg.getBBox) {
      try {
        var bb = svg.getBBox()
        c.setAttribute('viewBox', '0 0 ' + (bb.width + bb.x) + ' ' + (bb.height + bb.y))
      } catch (e) {}
    }

    // Capture the diagram's natural rendered size (post-CSS) before reparenting.
    var rect = svg.getBoundingClientRect()
    baseW = rect.width || svg.clientWidth || 0
    baseH = rect.height || svg.clientHeight || 0
    if (!baseW || !baseH) {
      var vb = c.getAttribute('viewBox')
      if (vb) {
        var parts = vb.trim().split(/\s+/)
        baseW = parseFloat(parts[2]) || 800
        baseH = parseFloat(parts[3]) || 600
      } else {
        baseW = 800
        baseH = 600
      }
    }

    // Strip explicit width/height attributes so style.width/height controls
    // sizing without competing with the attributes.
    c.removeAttribute('width')
    c.removeAttribute('height')

    wrap.innerHTML = ''
    wrap.appendChild(c)
    svgEl = c
    s = 1
    applyZoom()

    overlay.style.display = 'flex'
    document.documentElement.style.overflow = 'hidden'
    document.body.style.overflow = 'hidden'

    // After the box has been laid out (so clientWidth/Height are accurate),
    // scale the SVG to fit the available area. computeFit clamps to [MIN, MAX]
    // and works in either direction — enlarging column-clamped wide diagrams
    // and shrinking diagrams that would otherwise overflow the viewport.
    requestAnimationFrame(function () {
      fitScale = computeFit()
      s = fitScale
      applyZoom()
      recenter()
    })
  }

  function hide () {
    overlay.style.display = 'none'
    document.documentElement.style.overflow = ''
    document.body.style.overflow = ''
    wrap.innerHTML = ''
    svgEl = null
  }

  document.getElementById('mzm-close').onclick = hide
  document.getElementById('mzm-in').onclick = function () { zoomTo(s + 0.25) }
  document.getElementById('mzm-out').onclick = function () { zoomTo(s - 0.25) }
  document.getElementById('mzm-reset').onclick = function () {
    s = computeFit()
    fitScale = s
    applyZoom()
    requestAnimationFrame(recenter)
  }

  // Wheel zoom — toward viewport center.
  box.addEventListener('wheel', function (e) {
    e.preventDefault()
    e.stopPropagation()
    zoomTo(s + (e.deltaY < 0 ? 0.15 : -0.15))
  }, { passive: false })

  // Drag-to-pan: change the box's scroll position rather than transforming
  // the SVG, so panning composes naturally with native scrollbars.
  box.addEventListener('mousedown', function (e) {
    if (box.scrollWidth <= box.clientWidth && box.scrollHeight <= box.clientHeight) return
    drag = true
    dragStartX = e.clientX
    dragStartY = e.clientY
    dragStartScrollX = box.scrollLeft
    dragStartScrollY = box.scrollTop
    if (svgEl) svgEl.style.cursor = 'grabbing'
    e.preventDefault()
  })
  document.addEventListener('mousemove', function (e) {
    if (!drag) return
    box.scrollLeft = dragStartScrollX - (e.clientX - dragStartX)
    box.scrollTop = dragStartScrollY - (e.clientY - dragStartY)
  })
  document.addEventListener('mouseup', function () {
    if (!drag) return
    drag = false
    if (svgEl) svgEl.style.cursor = 'grab'
  })

  // Click on the dim background (not on the SVG) closes the overlay.
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay || e.target === box || e.target === wrap) hide()
  })

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') hide()
    if (overlay.style.display !== 'flex') return
    if (e.key === '+' || e.key === '=') zoomTo(s + 0.25)
    if (e.key === '-') zoomTo(s - 0.25)
    if (e.key === '0') {
      s = computeFit()
      fitScale = s
      applyZoom()
      requestAnimationFrame(recenter)
    }
  })

  function attach () {
    var els = document.querySelectorAll('div.mermaid')
    for (var i = 0; i < els.length; i++) {
      var el = els[i]
      if (el.getAttribute('data-zoomable')) continue
      if (!findSvg(el)) continue
      el.setAttribute('data-zoomable', '1')
      el.style.cursor = 'pointer'
      el.title = 'Click to zoom diagram'
      ;(function (target) {
        target.addEventListener('click', function (e) {
          e.preventDefault()
          e.stopPropagation()
          show(target)
        })
      })(el)
    }
  }

  setInterval(attach, 1000)
  setTimeout(attach, 500)
  setTimeout(attach, 2000)
  setTimeout(attach, 5000)
})()
