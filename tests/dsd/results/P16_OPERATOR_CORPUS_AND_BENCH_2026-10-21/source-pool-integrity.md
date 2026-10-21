# Broken DSD files

Scan of 5,881 DSD files (5,749 under ~/torrents, 132 under ~/library) on
2026-10-21. Headers only; no file was opened for writing or modified.

A DSF header declares the total file size at offset 12, and a DFF FRM8
header declares its own length, so truncation is detectable without reading
the audio. That check found three damaged files that a zero-byte test alone
would have missed.

## Genuinely broken: 21 files

### Empty (17) — zero bytes on disk

  /home/daedalus/torrents/Dire Straits Dire Straits/01 - Down To The Waterline.dsf
  /home/daedalus/torrents/Dire Straits Dire Straits/02 - Water Of Love.dsf
  /home/daedalus/torrents/Dire Straits Dire Straits/03 - Setting Me Up.dsf
  /home/daedalus/torrents/Dire Straits Dire Straits/04 - Six Blade Knife.dsf
  /home/daedalus/torrents/Dire Straits Dire Straits/05 - Southbound Again.dsf
  /home/daedalus/torrents/Dire Straits Dire Straits/06 - Sultans Of Swing.dsf
  /home/daedalus/torrents/Dire Straits Dire Straits/07 - In The Gallery.dsf
  /home/daedalus/torrents/Dire Straits Dire Straits/08 - Wild West End.dsf
  /home/daedalus/torrents/Dire Straits Dire Straits/09 - Lions.dsf
  /home/daedalus/torrents/Genesis Selling England By The pound/01 - Dancing With The Moonlit Knight.dsf
  /home/daedalus/torrents/Genesis Selling England By The pound/02 - I Know What I Like (In Your Wardrobe).dsf
  /home/daedalus/torrents/Genesis Selling England By The pound/03 - Firth Of Fifth.dsf
  /home/daedalus/torrents/Genesis Selling England By The pound/04 - More Fool Me.dsf
  /home/daedalus/torrents/Genesis Selling England By The pound/05 - The Battle Of Epping Forest.dsf
  /home/daedalus/torrents/Genesis Selling England By The pound/06 - After The Ordeal.dsf
  /home/daedalus/torrents/Genesis Selling England By The pound/07 - The Cinema Show   Aisle Of Plenty.dsf
  /home/daedalus/torrents/Pink Floyd - The Dark Side of the Moon (1973)/08 - Any Color you like.dsf

### Truncated (2) — incomplete, header declares more than is present

  /home/daedalus/torrents/Genesis ...and then there were three/07 - Many Too Many.dsf
      header declares 297746960, file is 297640464 (-106496)
  /home/daedalus/library/miles/Miles Davis - Rubberband (1985) [DSF] {Record Store Day EP  DSD128}/B1 - Rubberband of Life Instrumental.dsf
      header declares 479816336, file is 403701760 (-76114576)

### Oversize (1) — more bytes than the header declares

  /home/daedalus/torrents/Genesis ...and then there were three/05 - Burning Rope.dsf
      header declares 604291598, file is 608526862 (+4235264)

### Bad header (1)

  /home/daedalus/torrents/Roy Haynes Quartet 'Out Of The Afternoon' (1962, 2023)/02. Fly Me To The Moon (In Other Words).dsf
      magic b'\x00\x00\x00\x00'

## Not broken: 14 DST-compressed DFF

These are intact. SoX has no DST decoder, so it refuses them with
"invalid DSDIFF chunk layout", which is a misleading message for an
unsupported compression rather than a damaged file. Listed so they are not
mistaken for corruption.

  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/A4 - Backwards Traveller.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/A5 - Cuff Link.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/A6 - Children Children.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/A3 - I'm Carrying.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/A8 - I've Had Enough.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/B4 - Name And Address.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/A2 - Cafe On The Left Bank.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/B2 - Famous Groupies.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/A1 - London Town.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/B3 - Deliver Your Children.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/B5 - Don't Let It Bring You Down.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/A7 - Girlfriend.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/B1 - With A Little Luck.dff
  /home/daedalus/torrents/Wings - London Town (1978, Japan 1st, DST128)/B6 - Morse Moose And The Grey Goose.dff

Everything else read cleanly: 5,846 of 5,881.
