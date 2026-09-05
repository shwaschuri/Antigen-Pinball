# Build Antigen Pinball for the browser

From this folder, install the web packager and create the browser build:

```bash
python -m pip install --upgrade -r requirements-web.txt
python -m pygbag .
```

Pygbag writes the deployable website to `build/web/`. Open the local address it prints and press a key or click the title screen before expecting game audio.

To publish it with GitHub Pages, copy the *contents* of `build/web/` into a `docs/` folder in the `Antigen-Pinball` repository. Then open **Settings → Pages** and choose `main` and `/docs` as the publishing source.

The game now uses a browser-compatible async frame loop. It begins in a fixed-size canvas; browser fullscreen should be provided by the host page after a user action.
