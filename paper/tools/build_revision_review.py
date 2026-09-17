"""Create a concise Chinese review PDF from existing revised figure previews."""
from pathlib import Path
import argparse

from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader

PAPER = Path(__file__).resolve().parents[1]
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
FONT = "STSong-Light"
INK = colors.HexColor("#24282D")
MUTED = colors.HexColor("#616A74")
RULE = colors.HexColor("#D7DDE3")
ACCENT = colors.HexColor("#176B7D")
PAGE_W, PAGE_H = landscape(A4)
STYLE = ParagraphStyle("body",fontName=FONT,fontSize=10,leading=15,
                       textColor=INK,wordWrap="CJK",spaceAfter=0)
SMALL = ParagraphStyle("small",parent=STYLE,fontSize=9,leading=13)


def main(output):
    output.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(output),pagesize=(PAGE_W,PAGE_H))
    c.setTitle("OneStroke2026 论文与图稿修订对照")
    c.setAuthor("OneStroke2026 revision review")
    def para(text,x,y,width,style=STYLE):
        p=Paragraph(text,style);_,h=p.wrap(width,500);p.drawOn(c,x,y-h);return y-h
    def line(y):
        c.setStrokeColor(RULE);c.setLineWidth(.5);c.line(34,y,PAGE_W-34,y)
    def frame(title,page,subtitle):
        c.setFillColor(INK);c.setFont(FONT,23);c.drawString(34,PAGE_H-48,title)
        c.setFont(FONT,9);c.setFillColor(MUTED);c.drawString(34,PAGE_H-68,subtitle)
        line(PAGE_H-83)
        c.setFont(FONT,8);c.drawString(34,24,"OneStroke2026  |  2026-09-05  |  审阅稿")
        c.drawRightString(PAGE_W-34,24,str(page))
    frame("保留研究主线，让图和文字更容易读懂",1,
          "正文 20 页 · 补充材料 4 页 · 重点重绘图 2 / 3 / 6 · 全部七图已审阅")
    y=para("本轮保持 C1-C4 / RQ1-RQ4、方法流程、实验数值和引用。图 2 改为三个叙事区，图 3 梳理数据来源，图 6 突出评分机制与对照证据。文字修改已落实到 LaTeX 源文件，尚未推送 GitHub。",34,PAGE_H-101,PAGE_W-68)
    rows=[
      ["图", "读者要看懂什么", "本轮处理"],
      ["1", "问题、流程与可检查输出", "保留流程图；精简图注，明确跨风格差异是比较任务的示意。"],
      ["2", "交叉处为何有多个标签", "重绘：标注来源 → 重叠交叉 → 六通道；单个交叉作为视觉中心。"],
      ["3", "数据如何清洗、各来源有何区别", "重绘：明确 894-54=840、840-12-59=769；保留 40 类与全部 7 对。"],
      ["4", "模型在具体位置的输出差别", "保留真实模型输出及固定样例；继续区分单例观察与整集指标。"],
      ["5", "配准能补偿什么、仍会失去什么", "保留定量对照；收窄对更宽且更粗搜索的解释。"],
      ["6", "ASDS 怎样计算、是否依赖解析", "重绘机制及三个散点图；保留 150 对，突出配对差值与置信区间。"],
      ["7", "定位为什么成功或失败", "保留成功/失败证据；压缩图注，明确固定顺序失效分类。"],
    ]
    cells=[[Paragraph(x,SMALL) for x in row] for row in rows]
    tab=Table(cells,colWidths=[28,205,PAGE_W-68-233],hAlign="LEFT")
    tab.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EAF0F3")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F7F9FA")]),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
        ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("LINEBELOW",(0,0),(-1,0),.5,RULE),
    ]));_,h=tab.wrap(PAGE_W-68,500);tab.drawOn(c,34,y-16-h)
    y=y-16-h-17
    y=para("文字重点：压缩重复论述；“关联接近”不写成统计等效；区分解析、评分和受控掩膜诊断的验证层次；更宽搜索同时更粗；名义 p 值与聚类置信区间的含义分别说明。",34,y,PAGE_W-68,SMALL)
    para("验收依据：实际版宽可读、语义稳定、来源可追溯、矢量可编辑。图形品质没有统一的“超越某刊会”等级刻度。完整逐图建议、修订说明、图源和可编译源码见随附审阅包。",34,y-8,PAGE_W-68,SMALL)
    c.showPage()

    comparisons=[
      ("图 2：从 12 个面板到三个阅读步骤", "figure3_channel_definition", "figure2_channel_definition",
       "标注来源、交叉重叠、六通道输出各自承担一个问题；黑色交叉直接对应 vec1 + vec3。",
       "保留原生字形和掩膜像素，未重画笔画；端点圈、局部框均为显示标记。原宽范围放大图改为局部精确裁剪。"),
      ("图 3：数据来源与 QC 一次讲清", "figure2_dataset_overview", "figure3_dataset_overview",
       "取消与图 2 重复的采集示意，建立 QC → 40 类项目语料 → 7 对外部参考的清晰层级。",
       "保留原有全部 54 张图片及对应身份；逐张核验原生 RGB 哈希。外部参考继续明确为缓存解析掩膜，不作为分割真值。"),
      ("图 6：把机制和对照证据连起来", "figure6_asds_direct_ink", "figure6_asds_direct_ink",
       "上排解释 ASDS，底排完整呈现 150 对样本；配对差值和区间放在读者容易找到的位置。",
       "热图颜色按各自面板最大值归一化，不新增未知绝对数值；投影曲线共同缩放。结果说明当前队列关联接近，不构成统计等效或外部验证。"),
    ]
    for page,(title,old,new,benefit,integrity) in enumerate(comparisons,2):
        frame(title,page,"左：仓库当前图  |  右：本轮修订图  |  数据、样例与主要论证保持一致")
        left=34;gap=26;boxw=(PAGE_W-68-gap)/2
        for x,label,src in [
          (left,"修改前",PAPER/"figures/redrawn"/(old+".png")),
          (left+boxw+gap,"本轮修订",PAPER/"figures/revision"/(new+".png"))]:
            c.setFont(FONT,11);c.setFillColor(ACCENT if label=="本轮修订" else MUTED)
            c.drawString(x,PAGE_H-108,label)
            im=ImageReader(str(src));iw,ih=im.getSize();scale=min(boxw/iw,307/ih)
            w,h=iw*scale,ih*scale
            c.drawImage(im,x+(boxw-w)/2,160+(307-h)/2,width=w,height=h,mask="auto")
        line(141)
        para("阅读收益："+benefit,34,125,PAGE_W-68)
        para("真实性与边界："+integrity,34,89,PAGE_W-68,SMALL)
        c.showPage()
    c.save()
    print(output)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True)
    main(p.parse_args().output.resolve())
