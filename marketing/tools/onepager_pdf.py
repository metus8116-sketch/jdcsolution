# -*- coding: utf-8 -*-
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, KeepTogether)
from reportlab.lib.styles import ParagraphStyle

F = "WQY"
pdfmetrics.registerFont(TTFont(F, "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", subfontIndex=0))

GREEN = colors.HexColor("#0a9b54")
DGREEN = colors.HexColor("#06420f")
RED = colors.HexColor("#b00020")
LIGHT = colors.HexColor("#eafaf1")
GREY = colors.HexColor("#444444")

def P(t, size=9.2, lead=12, color=colors.black, bold=False, space=1):
    return Paragraph(t, ParagraphStyle("x", fontName=F, fontSize=size, leading=lead,
                     textColor=color, spaceAfter=space))

def H(t):
    return Paragraph(t, ParagraphStyle("h", fontName=F, fontSize=10, leading=13,
                     textColor=DGREEN, backColor=LIGHT, borderColor=GREEN,
                     borderWidth=0, leftIndent=2, spaceBefore=3, spaceAfter=2,
                     leading_=13))

OUT = "/home/user/jdcsolution/marketing/오산리_현장탐문_원페이저.pdf"
doc = SimpleDocTemplate(OUT, pagesize=A4, topMargin=9*mm, bottomMargin=8*mm,
                        leftMargin=11*mm, rightMargin=11*mm)
S = []

def heading(t):
    tb = Table([[Paragraph(t, ParagraphStyle("hh", fontName=F, fontSize=10.2,
            leading=13, textColor=DGREEN))]], colWidths=[doc.width])
    tb.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),LIGHT),
        ("LINEBEFORE",(0,0),(0,-1),2.2,GREEN),
        ("TOPPADDING",(0,0),(-1,-1),2.2),("BOTTOMPADDING",(0,0),(-1,-1),2.2),
        ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),3),
    ]))
    return tb

# Title
S.append(P("오산리 현장 탐문 미션 — 죽전에스치과", size=15.5, lead=18, color=GREEN, space=1))
tl = Table([[Paragraph("모현읍 오산리(오산2리) 주민을 우리 동네 단골로 — 현장 정보 수집용 · 직원용 A4",
        ParagraphStyle("s", fontName=F, fontSize=8.2, textColor=GREY))]], colWidths=[doc.width])
tl.setStyle(TableStyle([("LINEBELOW",(0,0),(-1,-1),1.4,GREEN),("BOTTOMPADDING",(0,0),(-1,-1),2),
        ("LEFTPADDING",(0,0),(-1,-1),0)]))
S.append(tl)
S.append(P("<b>담당:</b> ____________ &nbsp;|&nbsp; <b>일자:</b> ____________ &nbsp;|&nbsp; <b>소요:</b> 반나절 &nbsp;|&nbsp; <b>준비물:</b> 명함·메모지·휴대폰(지도/사진)·이 종이",
        size=8.3, lead=11, color=GREY, space=2))

S.append(heading("① 30초 배경 — 왜 가는가"))
for t in [
 "• 오산리 = <b>죽전·분당 생활권, 우리 치과까지 차로 약 10분.</b> '멀어서 안 오는' 게 아니라 <b>'가까운데 아직 모르는'</b> 동네.",
 "• 아파트 아님 → <b>단독·전원주택 + 타운하우스.</b> 광고 살포(×) → <b>거점(마을회관·단지 총무) 1곳 잡기(○).</b>",
 "• 주민 2층: <b>① 어르신·원주민</b>(틀니·임플란트·잇몸 / 마을회관·이장·부녀회) &nbsp; <b>② 전원주택·타운하우스 가구</b>(검진·교정·소아·심미 / 단톡방·총무).",
]:
    S.append(P(t, size=9, lead=11.5, space=1))

S.append(heading("② 나가서 알아올 것 — 탐문 체크리스트"))
for t in [
 "□ <b>오산2리 마을회관·경로당</b> 위치, 운영 요일·시간, <b>이장 / 부녀회장 / 노인회장 이름·연락처</b>(키맨).",
 "□ <b>타운하우스·전원주택 단지</b> — 단지명 / 대략 세대수 / <b>총무·대표 연락처</b> / <b>입주민 단톡방·밴드 유무.</b>",
 "□ <b>면소재지 거점</b> — 약국·하나로/농협·보건지소·소아과·미용실·주유소/카센터 위치(제휴 후보).",
 "□ <b>현수막 걸 만한 진입로·게시대</b> 위치 + 지자체 게시 신청처.",
 "□ <b>경쟁 치과</b> — 주민들이 어느 치과 다니는지 슬쩍 / 사진(마을회관·단지 입구·게시판·상권).",
]:
    S.append(P(t, size=9, lead=11.5, space=1))

S.append(heading("③ 이렇게 말하세요 — 컨택 스크립트 (광고 아님, 인사 톤)"))
for t in [
 "• <b>마을회관/이장:</b> <i>\"안녕하세요, 죽전에스치과인데요. 어르신들 대상으로 무료 구강검진 한 번 열어드리고 싶어 인사드리러 왔어요. 어느 분께 말씀드리면 될까요?\"</i>",
 "• <b>단지 총무:</b> <i>\"옆 동네 치과인데, 입주민분들께 무료 검진 데이 한 번 해드리고 싶어요. 단톡방이나 게시판 안내가 가능할까요?\"</i>",
 "• <b>상가/약국:</b> <i>\"명함 몇 장 두고 가도 될까요? 서로 손님 소개해요.\"</i> → 끝에 <b>명함 전달 + 연락처 받기.</b> 거절해도 웃으며 감사.",
]:
    S.append(P(t, size=8.9, lead=11.3, space=1, color=DGREEN))

# Two-column ④ ⑤
left = [Paragraph("④ 절대 하지 말 것 (의료법)", ParagraphStyle("c",fontName=F,fontSize=9.6,textColor=DGREEN,leading=12,spaceAfter=2)),
        P("<font color='#b00020'><b>×</b></font> '주민 할인 / 스케일링 무료 / 본인부담 면제' 등 <b>가격 혜택 약속</b> (= 환자 유인, 제27조).", 8.4, 10.5, space=2),
        P("<font color='#b00020'><b>×</b></font> 증상 듣고 <b>'임플란트 하셔야 해요' 식 진단·단정.</b>", 8.4, 10.5, space=2),
        P("<font color='#0a7d2c'><b>○</b></font> 줄 수 있는 건 <b>무료 검진(봉사)·정보·우선 예약 편의·소액 기념품(칫솔/치약)</b>뿐.", 8.4, 10.5, space=1)]
right = [Paragraph("⑤ '특별 대우'는 가격 말고 관계로", ParagraphStyle("c",fontName=F,fontSize=9.6,textColor=DGREEN,leading=12,spaceAfter=2)),
        P("우리 무기 = <b>\"오산리 이웃 채널 — 동네 주치의\".</b> 가격을 깎는 게 아니라 <b>카톡으로 검진 시기 먼저 챙기고, 우선 예약 도와주는</b> 동네 치과. (합법 + 더 강력)", 8.4, 10.8)]
tw = Table([[left, right]], colWidths=[doc.width*0.5-2, doc.width*0.5-2])
tw.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor("#fdeef0")),
        ("BACKGROUND",(1,0),(1,0),colors.HexColor("#eef6f0")),
        ("BOX",(0,0),(0,0),0.6,colors.HexColor("#e3b0b8")),
        ("BOX",(1,0),(1,0),0.6,colors.HexColor("#b7dcc4")),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
S.append(Spacer(1,3)); S.append(tw)

S.append(heading("⑥ 돌아와서 제출 — 보고 양식"))
rows = ["마을회관 위치·운영시간","이장/부녀회장/노인회장 (이름·연락처)",
        "타운하우스 단지명·세대수·총무·단톡방","제휴 후보(약국·소아과·상가 등)",
        "현수막 위치 후보 / 경쟁 치과"]
data = [[P("<b>"+r+"</b>",8.4,10.5), ""] for r in rows]
rt = Table(data, colWidths=[doc.width*0.44, doc.width*0.56], rowHeights=[7.2*mm]*len(rows))
rt.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#999999")),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#f1f7f3")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4)]))
S.append(Spacer(1,1)); S.append(rt)

foot = Table([[P("◎ <b>1차 목표 = 키맨 연락처 확보.</b> '마을회관 무료 검진 데이'와 '타운하우스 1개 단지 검진 데이'로 들어갈 사람만 연결하면 성공. <b>계약·약속은 하지 말 것 — 연결고리(사람)만 만들어 오기.</b>",
        9, 12, color=colors.white)]], colWidths=[doc.width])
foot.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),GREEN),
        ("TOPPADDING",(0,0),(-1,-1),3.5),("BOTTOMPADDING",(0,0),(-1,-1),3.5),
        ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("ROUNDEDCORNERS",[3,3,3,3])]))
S.append(Spacer(1,4)); S.append(foot)

doc.build(S)
print("OK", OUT)
