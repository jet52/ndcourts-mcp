const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel } = require("docx");

const citations = [
  "1 N.D. 266",
  "105 N.W. 621",
  "105 N.W. 734",
  "11 N.D. 22",
  "11 N.D. 458",
  "115 N.W. 844",
  "116 N.W. 85",
  "13 N.D. 257",
  "133 N.W. 548",
  "14 N.D. 445",
  "143 N.W. 350",
  "148 N.W. 834",
  "151 N.W. 29",
  "159 N.W. 2",
  "160 N.W. 143",
  "163 N.W. 832",
  "169 N.W. 577",
  "170 N.W. 118",
  "171 N.W. 832",
  "176 N.W. 7",
  "2 N.D. 397",
  "20 N.D. 555",
  "21 N.D. 205",
  "21 N.D. 211",
  "28 N.D. 324",
  "31 N.D. 240",
  "31 N.D. 504",
  "32 N.D. 79",
  "38 N.D. 425",
  "38 N.D. 499",
  "39 N.D. 386",
  "41 N.D. 599",
  "42 N.D. 83",
  "44 N.D. 5",
  "51 N.W. 718",
  "53 N.W. 177",
  "54 N.W. 315",
  "6 N.D. 317",
  "71 N.W. 769",
  "72 N.W. 931",
  "73 N.W. 87",
  "73 N.W. 91",
  "75 N.W. 807",
  "79 N.W. 849",
  "9 N.D. 165",
  "9 N.D. 268",
  "92 N.W. 1134",
  "92 N.W. 453",
  "96 N.W. 299",
  "97 N.W. 543",
];

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Times New Roman", size: 24 },
      },
    },
  },
  sections: [
    {
      properties: {
        page: {
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      children: [
        new Paragraph({
          spacing: { after: 200 },
          children: [
            new TextRun({
              text: "ND Supreme Court — Pre-1920 Citation Sample (n=50)",
              bold: true,
              size: 28,
            }),
          ],
        }),
        new Paragraph({
          spacing: { after: 400 },
          children: [
            new TextRun({
              text: "For Westlaw Quick Check validation against ndcourts-mcp database.",
              italics: true,
              size: 20,
              color: "666666",
            }),
          ],
        }),
        ...citations.map(
          (cite) =>
            new Paragraph({
              spacing: { after: 120 },
              children: [new TextRun({ text: cite })],
            })
        ),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("westlaw-quickcheck-sample.docx", buffer);
  console.log("Created westlaw-quickcheck-sample.docx with 50 citations");
});
