   10 rem save"luna081426",8,1
   20 clr:printchr$(8):rv$="luna2":bl$="                                        "
   30 sys16896:gosub1020:gosub990
   40 print"{clr}":v=53248:js=56320:sn=1504:s=54272:c$="{left} ":poke53280,11:poke53281,0
   50 t1$="{rvon}vel {rvof} ":t2$="{rvon}fuel{rvof} ":t3$="{rvon}horz{rvof} ":ep=250:hp=-20:lc=55296
   60 pn=2040:fe=1000:fu=fe:nm=4:nf=.:n2=25:gosub1100
   70 pokev+41,1:pokev+42,6:poke2042,253:poke2043,254
   80 pokev+4,60:pokev+5,60:pokev+6,60:pokev+7,60
   90 po=28:pp=ep:hm=hp:ep=ep-23:ifep=20thenep=250
  100 hp=hp+4:ifhp>25thenhp=-25
  110 e2=.:pokev+39,0:pokev+40,0:pokev+16,0
  120 ifn2>47thenn2=37
  130 p=187:m2=n2:n2=n2+4:pokev+17,peek(v+17)or16
  135 gosub1500:gosub1600
  160 getz$
  170 ifz$="{rght}"thenp=p+1:ifp=190thenp=189:goto200
  172 ifp=195thenp=187:goto200
  180 ifz$="{down}"thenp=p-1:ifp=186thenp=194:goto200
  182 ifp=192thenp=193:goto200
  190 ifz$="{f1}"thenpoke1024,134:poke55296,7:goto1270
  200 iffe<1goto230
  220 ifpeek(653)thenpokev+21,15:q=8:goto240
  230 q=.:m2=m2+.6:pokev+21,13:pokes+4,128:goto330
  240 pokes+24,15:pokes+5,128:pokes+6,128:pokes+1,8:pokes,200:pokes+4,129
  245 onp-186goto250,260,280,330,330,330,290,270
  250 m2=m2-.6:fe=fe-1:goto330
  260 m2=m2-.6:hm=hm+1:fe=fe-2:goto330
  270 m2=m2-.6:hm=hm-1:fe=fe-2:goto330
  280 m2=m2-.2:hm=hm+2:fe=fe-3:goto330
  290 m2=m2-.2:hm=hm-2:fe=fe-3:goto330
  330 onsgn(m2)+2goto332,350,340
  332 po=po-(.1+(-m2/20)):goto350
  340 po=po+(.1+(m2/20))
  350 onsgn(hm)+2goto360,430,400
  360 pp=pp-(-hm/4)
  370 ife2=.thenifpp<.thene2=1:pp=87+pp:pokev+16,243:goto430
  380 ife2thenifpp<.thene2=.:pp=255+pp::pokev+16,0
  390 goto430
  400 pp=pp+(hm/4)
  410 ife2=.thenifpp>255thene2=1:pp=pp-255:pokev+16,243:goto430
  420 ife2thenifpp>87thene2=.:pp=pp-87:pokev+16,0
  430 pokev,pp:pokev+1,po:pokev+2,pp:pokev+3,po
  440 pokepn,p:pokepn+1,p+q
  450 pokev+39,12:pokev+40,8
  460 ifpo<25thenpo=25
  480 ifpo>230thenhm=10:goto1320
  500 ifm2<3thenprint"{grn}";:goto530
  510 print"{yel}";
  515 ifm2>5thenprint"{red}";
  530 print"{home}{down}{down}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"t1$
  531 print"{home}{down}{down}{down}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"int(m2);c$
  535 iffe<1thenfe=.
  540 iffe>399thenprint"{grn}";:goto570
  550 iffe<100thenprint"{red}";:goto570
  560 print"{yel}";
  570 print"{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"t2$;
  571 print"{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"fe;c$
  580 ifhm>99thenhm=98:goto610
  590 ifhm<-99thenhm=-98:goto610
  600 ifhm=.thenprint"{grn}";:goto620
  605 ifhm>-3thenifhm<3thenprint"{yel}";:goto620
  610 print"{red}";
  620 print"{home}{down}{down}{down}{down}{down}{down}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"t3$;
  621 print"{home}{down}{down}{down}{down}{down}{down}{down}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}{rght}"hm;c$
  630 ifpeek(v+31)and1thenifpo>120goto640
  635 goto160
  640 ifhm>2goto1320
  641 ifhm<-2goto1320
  642 ifp<>187goto1320
  644 ifint(m2)>5goto1320
  649 pf=int(pp):ife2thenpf=pf+256
  650 ifpf>70thenifpf<89thentp=tp+600:lz=1:goto720
  670 ifpf>150thenifpf<169thentp=tp+600:lz=3:goto720
  680 ifpf>206thenifpf<225thentp=tp+600:lz=4:goto720
  690 ifpo>200thenifpf>238thenifpf<248thentp=tp+700:lz=5:goto720
  695 ifpo>226thenifpf>109thenifpf<129thentp=tp+800:lz=2:iffe>399then720
  696 iflz=2thenfe=1000:e7=1:goto720
  700 goto1320
  710 nm=nm-1:n2=n2-7:lz=.
  720 pokev+21,13:pokev+16,0
  730 pokes+4,128:forx=1to500:next
  740 iflz=1thenifpf=79orpf=80thenbs=400
  744 iflz=2thenifpf=119orpf=120thenbs=600
  746 iflz=3thenifpf=159orpf=160thenbs=400
  748 iflz=4thenifpf=215orpf=216thenbs=400
  750 iflz=5thenifpf=243orpf=244thenbs=500
  752 tp=tp-abs(int(m2))*30
  753 tp=tp-abs(hm)*30
  754 tp=tp-(fu-fe)
  755 tp=tp+bs
  760 pt=pt+tp:ifpt<1thenpt=.
  775 bs=bs-(fu-fe):ifbs>.thena$="{cyn} "+str$(bs)+" bonus":gosub982
  778 a$="{cyn}"+str$(int(tp))+" points":gosub982
  780 ife7thene7=.:a$="{lgrn}fuel tanks full":gosub982
  785 ifnm<.orfe<1thennf=1:nm=.
  790 ifnf=1thena$="{rvof}{orng}game over":ep=250:hp=-20:ifpt>hsthenhs=pt:gosub1500
  795 ifnfgoto982
  840 tp=.:fu=fe:bs=.:forx=1to200:next:goto90
  960 getz$
  970 ifz$="{f7}"thenpt=.:tp=.:nm=4:nf=.:fe=1000:n2=25:gosub986:goto840
  980 goto960
  982 print"{home}{down}{down}{down}{down}{down}{down}{down}{down}";spc((42-len(a$))/2);:forx=1tolen(a$):printmid$(a$,x,1);
  983 gosub990:next
  984 forx=1to3000:next:ifnfgoto960
  986 print"{home}{down}{down}{down}{down}{down}{down}{down}{down}"bl$;:return
  990 forl=54272to54296:pokel,0:next
 1000 poke54296,10:poke54277,64:poke54273,17:poke54272,37:poke54276,17
 1010 fort=1to20:next:poke54276,16:return
 1020 print"{clr}":poke53280,11:poke53281,0
 1030 poke214,5:print:printtab(11)"{lblu}l u n a l i g h t";
 1040 poke214,16:print:print"{lblu}   public domain 2024 steven hardison"
 1050 print"{down}";
 1060 printtab(11);
 1070 print"press {rvon}f7{rvof} to start"
 1080 getf$:iff$="{f7}"thenreturn
 1090 goto1080
 1100 print"{lblu}{home}{down}{down}{down}{down}{down}{down}{down}{down}{down}{down}{down}{down}"spc(12)"    {orng}{CBM-P}{yel}{CBM-P}{CBM-P}{CBM-P}{orng}{CBM-P}"
 1120 print"{lblu}                {rvon}     "
 1130 print"{lblu}      {orng}{CBM-P}{yel}{CBM-P}{CBM-P}{CBM-P}{orng}{CBM-P}     {lblu}{rvon}     {rvof}  {orng}{CBM-P}{yel}{CBM-P}{CBM-P}{CBM-P}{orng}{CBM-P}"
 1140 print"{lblu}      {rvon}     {rvof}     {CBM-*}{rvon}    {rvof}  {rvon}     "
 1150 print"{lblu}{rvon}{CBM-*}{rvof}      {rvon}    {rvof}       {CBM-*}{rvon}       {rvof}{SHIFT-POUND}"
 1170 print"{lblu}{rvon}   {rvof}  {rvon}       {rvof}       {rvon}     {rvof}           {rvon}{SHIFT-POUND}  {CBM-*}"
 1180 print"{lblu}{rvon}             {rvof}     {rvon}{SHIFT-POUND}       {CBM-*}{rvof}       {rvon}{SHIFT-POUND}     ";
 1190 print"{lblu}{rvon}          {rvof}{SHIFT-POUND}       {rvon}        {rvof}{SHIFT-POUND}      {rvon}       ";
 1200 print"{lblu}{rvon}          {rvof}        {rvon}        {CBM-*}{rvof}{orng}{CBM-P}{yel}{CBM-P}{CBM-P}{CBM-P}{orng}{CBM-P}{rvon}{lblu}{SHIFT-POUND}       ";
 1210 print"{lblu}{rvon}        {rvof}{SHIFT-POUND}        {rvon}{SHIFT-POUND}                      ";
 1220 print"{lblu}{rvon}        {rvof}         {rvon}                        ";
 1230 print"{lblu}{rvon}         {CBM-*}{rvof}{orng}{CBM-P}{yel}{CBM-P}{CBM-P}{CBM-P}{orng}{CBM-P}{rvon}{lblu}{SHIFT-POUND}                       ";
 1240 print"{rvon}                                       ";
 1250 poke56295,14:poke2023,160
 1260 print"{home}":return
 1270 getz$
 1280 ifz$="{f1}"thenpoke1024,160:poke55296,0:goto200
 1290 ifz$="{f7}"then20
 1300 ifz$="{home}"thenprintrv$;:stop
 1310 goto1270
 1320 pokes+4,128:forss=1to4:pokev+42+ss,7:next:pp=int(pp):pr=pp:pl=pp
 1325 pokepn+4,203:pokepn+5,213:pokepn+6,223:pokepn+7,233
 1330 ifpp+12>255thenpokev+16,96:pr=pp-256
 1340 pokev+10,pr+12:pokev+9,po-10:pokev+12,pr+12:pokev+15,po+10
 1350 ifpeek(v+16)<>.thenifpp-12<.thenpokev+16,96:pl=256+pp:goto1370
 1360 ifpp-12<.thenpl=15
 1370 pokev+14,pl-12:pokev+13,po+10:pokev+8,pl-12:pokev+11,po-10:pokev+21,252
 1380 pokev+28,240:pokev+37,11:pokev+38,2:pokev+39,0:pokev+40,0
 1390 forex=203to212:pokepn+4,ex:pokepn+5,ex+10:pokepn+6,ex+20:pokepn+7,ex+30
 1400 pokes+24,212-ex:pokes+4,129:pokes+5,15:pokes+1,5:pokes,20:ford=1to100:next:nextex
 1410 pokes+4,0:pokes+5,0:pokev+1,12:pokev+21,12
 1420 goto710
 1500 poke214,23:print:print"{rvon}{lblu}                                       ";
 1510 poke214,23:print:print"{rvon}{lblu} hi";hs;tab(17);"score";pt;:printtab(32);nm;"lems";
 1520 return
 1600 forx=1to5
 1610 onxgoto1700,1702,1704,1706,1708:goto1830
 1700 l1=566:l2=567:l3=568:l4=569:l5=570:goto1790
 1702 l1=496:l2=497:l3=498:l4=499:l5=500:goto1790
 1704 l1=827:l2=828:l3=829:l4=830:l5=831:goto1790
 1706 l1=583:l2=584:l3=585:l4=586:l5=587:goto1790
 1708 l1=931:l2=932:l3=933:l4=934:l5=935:goto1790
 1790 pokelc+l1,7:pokelc+l2,5:pokelc+l3,5:pokelc+l4,5:pokelc+l5,7
 1800 next
 1830 return
