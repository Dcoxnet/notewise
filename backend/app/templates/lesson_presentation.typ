#let data = json("presentation.json")
#let ink = rgb("#202A35")
#let muted = rgb("#687587")
#let accent = rgb("#3B66F5")
#let pale = rgb("#EAF0FF")
#let paper = rgb("#F7F8FC")

#set page(
  width: 13.333in,
  height: 7.5in,
  margin: (x: 0.78in, y: 0.42in),
  fill: paper,
  footer: context [
    #line(length: 100%, stroke: rgb("#DFE4EF"))
    #v(6pt)
    #grid(columns: (1fr, auto), text(size: 8pt, fill: muted)[NOTEWISE  ·  КОНСПЕКТ УРОКА], text(size: 8pt, fill: muted)[#counter(page).display("1")])
  ],
)
#set text(font: "DejaVu Sans", size: 14pt, fill: ink)
#set par(leading: 0.8em)

#let eyebrow(body) = text(body, size: 9pt, weight: "bold", fill: accent, tracking: 1pt)
#let slide_title(body) = text(body, size: 25pt, weight: "bold", fill: ink)

// Титульный слайд
#block(width: 100%)[
  #v(0.2in)
  #eyebrow[NOTEWISE  /  КРАТКИЙ ПЕРЕСКАЗ ЛЕКЦИИ]
  #v(16pt)
  #text(size: 30pt, weight: "bold", fill: ink)[#data.title]
  #v(9pt)
  #text(size: 16pt, fill: muted)[#data.subtitle]
  #v(18pt)
  #block(width: 78pt, height: 3pt, fill: accent)
  #v(16pt)
  #block(width: 86%)[#set text(size: 14pt)
    #set par(leading: 1em)
    #data.summary
  ]
  #v(14pt)
  #text(size: 9pt, fill: muted)[От исходной проблемы — к решениям, примерам и выводам]
]

#for (index, slide) in data.slides.enumerate() [
  #pagebreak()
  #block(width: 100%)[
    #grid(columns: (1fr, auto))[
      #eyebrow[РАЗДЕЛ  #(index + 1)  /  #data.slides.len()]
      #text(size: 9pt, weight: "bold", fill: muted)[#slide.timestamp]
    ]
    #v(9pt)
    #slide_title(slide.title)
    #v(11pt)
    #block(width: 100%, fill: pale, radius: 9pt, inset: (x: 15pt, y: 10pt))[
      #text(size: 15pt, weight: "bold", fill: ink)[#slide.claim]
    ]
    #v(10pt)
    #block(width: 100%, inset: (x: 2pt, y: 0pt))[
      #set text(size: 13pt, fill: ink)
      #set par(leading: 0.9em)
      #slide.explanation
    ]
    #if slide.diagram != "" [
      #v(5pt)
      #image(slide.diagram, width: 100%)
    ]
    #if slide.example != "" [
      #v(5pt)
      #block(width: 100%, fill: white, stroke: (paint: rgb("#E6EAF2"), thickness: 0.6pt), radius: 9pt, inset: (x: 13pt, y: 8pt))[
        #eyebrow[ПРИМЕР ИЗ ЛЕКЦИИ]
        #v(4pt)
        #text(size: 11pt, fill: muted)[#slide.example]
      ]
    ]
  ]
]

#if data.terms.len() > 0 [
  #pagebreak()
  #block(width: 100%)[
    #eyebrow[КОРОТКО О ТЕРМИНАХ]
    #v(13pt)
    #slide_title[Термины, которые объяснил лектор]
    #v(20pt)
    #for term in data.terms [
      #block(width: 100%, fill: white, stroke: (paint: rgb("#E6EAF2"), thickness: 0.6pt), radius: 8pt, inset: 12pt)[
        #text(size: 13pt, weight: "bold", fill: accent)[#term.term]
        #h(10pt)
        #text(size: 12pt)[#term.translation]
        #linebreak()
        #text(size: 11pt, fill: muted)[#term.explanation]
      ]
      #v(8pt)
    ]
  ]
]

#if data.action_items.len() > 0 [
  #pagebreak()
  #block(width: 100%)[
    #eyebrow[ПРАКТИКА]
    #v(13pt)
    #slide_title[Задания из лекции]
    #v(20pt)
    #for item in data.action_items [
      #block(width: 100%, fill: pale, radius: 8pt, inset: (x: 16pt, y: 12pt))[
        #text(size: 15pt)[#item]
      ]
      #v(10pt)
    ]
  ]
]
