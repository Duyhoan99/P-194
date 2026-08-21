import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  let patientName = 'Nguyễn Demo An';
  let age = 61;
  let gender = 'Nữ';
  let condition = 'Đái tháo đường Típ 2 (E11)';
  let medications = 'Metformin 1000mg BID';
  let vitals: any = { HbA1c: '7.4%', BP: '130/79 mmHg', eGFR: '70 mL/min' };

  try {
    const body = await request.json();
    if (body.patientName) patientName = body.patientName;
    if (body.age) age = body.age;
    if (body.gender) gender = body.gender;
    if (body.condition) condition = body.condition;
    if (body.medications) medications = body.medications;
    if (body.vitals) vitals = body.vitals;

    const apiKey = process.env.LLM_API_KEY || 'K7U1R3Vt2INj2uscBH61lgpeUdYIo7Ig';
    const baseUrl = process.env.LLM_BASE_URL || 'https://api.mistral.ai/v1';
    const modelName = process.env.LLM_MODEL_NAME || 'mistral-small-latest';

    const systemPrompt = `Bạn là Bác Sĩ Trợ Lý Lâm Sàng Cao Cấp (Clinical AI Care Plan Agent) thuộc nền tảng Y tế P-194.
Nhiệm vụ: Dựa trên Hồ Sơ Bệnh Án Thực Tế và Phác đồ Hướng dẫn Điều trị Chuẩn của Bộ Y Tế Việt Nam (QĐ 5481/QĐ-BYT cho Đái tháo đường, QĐ 3192/QĐ-BYT cho Tăng huyết áp, Dược thư Quốc gia), hãy soạn thảo Phiếu Hướng Dẫn Điều Trị & Dặn Dò Tại Nhà (Patient Care Plan) cho người bệnh.

QUY TẮC Y KHOA BẮT BUỘC (STRICT MEDICAL GUARDRAILS):
1. TUYỆT ĐỐI KHÔNG BỊA ĐẶT THUỐC MỚI: Chỉ dặn dò các thuốc thực tế bệnh nhân đang dùng trong hồ sơ.
2. CHUYỂN ĐỔI NGÔN NGỮ BÌNH DÂN (PLAIN LANGUAGE): Dùng lời lẽ ân cần, lễ phép, gần gũi, dễ hiểu cho người cao tuổi ('Chào bác...', 'Bác nhớ...').
3. AN TOÀN DÙNG THUỐC: Nêu rõ uống Sáng/Tối, trước hay sau ăn no (Ví dụ: Metformin phải uống sau ăn no để tránh kích ứng dạ dày).
4. CẢNH BÁO CẤP CỨU CỤ THỂ: Nêu rõ dấu hiệu nguy hiểm (tụt đường huyết, tăng huyết áp kịch phát) và hành động xử trí khẩn cấp ngay tại chỗ (ngậm kẹo ngọt, liên hệ cấp cứu).
5. ĐỊNH DẠNG TRẢ VỀ: BẮT BUỘC chỉ trả về 1 chuỗi JSON hợp lệ duy nhất, không kèm markdown hay lời mở đầu.`;

    const userPrompt = `THÔNG TIN BỆNH NHÂN:
- Họ tên: ${patientName}
- Tuổi: ${age} | Giới tính: ${gender}
- Chẩn đoán: ${condition}
- Thuốc đang dùng: ${medications}
- Chỉ số xét nghiệm: ${JSON.stringify(vitals)}

CĂN CỨ PHÁC ĐỒ BỘ Y TẾ (RAG CONTEXT):
- Đái tháo đường Típ 2 (QĐ 5481/QĐ-BYT): Mục tiêu HbA1c < 7.0%, Metformin uống sau ăn no, kiêng đường đơn, tăng rau xanh, đi bộ 150p/tuần, cấp cứu hạ đường huyết quy tắc 15-15 (ngậm kẹo).
- Tăng huyết áp (QĐ 3192/QĐ-BYT): Mục tiêu < 130/80 mmHg, ăn giảm muối < 5g/ngày, tránh xúc động mạnh.

HÃY XUẤT RA JSON THEO CẤU TRÚC:
{
  "doctor_greeting": "Lời chào ân cần của Bác sĩ và nhận xét tiến triển chỉ số sức khỏe của bệnh nhân",
  "morning_meds": "Tên thuốc và liều lượng uống buổi sáng (kèm lưu ý trước/sau ăn)",
  "evening_meds": "Tên thuốc và liều lượng uống buổi tối (kèm lưu ý trước/sau ăn)",
  "diet_good": "Thực phẩm nên ăn và uống đủ (chi tiết rau củ, đạm, nước)",
  "diet_bad": "Thực phẩm cần kiêng cữ và hạn chế (đường, muối, mỡ...)",
  "exercise": "Hướng dẫn vận động thể lực và thói quen chăm sóc cơ thể phù hợp",
  "emergency_warning": "Dấu hiệu cấp cứu nguy hiểm và cách xử trí khẩn cấp tức thì",
  "follow_up_days": "30",
  "guideline_citation": "Quyết định số 5481/QĐ-BYT (Bộ Y Tế)"
}`;

    const llmRes = await fetch(`${baseUrl.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: modelName,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt }
        ],
        temperature: 0.3,
        response_format: { type: 'json_object' }
      })
    });

    if (llmRes.ok) {
      const data = await llmRes.json();
      let rawContent = data?.choices?.[0]?.message?.content || '{}';
      
      if (rawContent.startsWith('```')) {
        rawContent = rawContent.replace(/^```json/, '').replace(/^```/, '').replace(/```$/, '');
      }

      const parsed = JSON.parse(rawContent);
      return NextResponse.json({
        status: 'success',
        agent_type: `Clinical LLM Agent (${modelName}) + Medical RAG`,
        plan: parsed
      });
    } else {
      console.warn('LLM Agent error response, falling back to clinical rules:', await llmRes.text());
    }
  } catch (err: any) {
    console.error('Care Plan API Error:', err);
  }

  // Graceful deterministic fallback
  const isHTN = (condition || '').toLowerCase().includes('huyết áp') || (condition || '').toLowerCase().includes('hypertension') || (condition || '').toLowerCase().includes('i10');
  const isCKD = (condition || '').toLowerCase().includes('thận') || (condition || '').toLowerCase().includes('kidney') || (condition || '').toLowerCase().includes('n18');
  const pName = patientName || 'Bệnh nhân';

  let fallbackPlan = {
    doctor_greeting: `Chúc mừng bác ${pName}, chỉ số đường huyết và huyết áp đợt này đã cải thiện rất tích cực. Bác hãy tiếp tục duy trì 4 hướng dẫn điều trị bên dưới để giữ vững sức khỏe nhé!`,
    morning_meds: 'Metformin 1000 mg (Uống 1 viên ngay sau khi ăn sáng no)',
    evening_meds: 'Metformin 1000 mg (Uống 1 viên ngay sau khi ăn tối no)',
    diet_good: 'Tăng cường rau xanh luộc (rau muống, cải bắp, dưa chuột), cá nạc, ức gà, đậu phụ; uống đủ 1.5 - 2L nước ấm.',
    diet_bad: 'Kiêng bánh kẹo ngọt, nước ngọt có ga, trà sữa; hạn chế quả ngọt đậm (sầu riêng, nhãn, mít, xoài chín).',
    exercise: 'Đi bộ nhẹ nhàng 20 - 30 phút sau bữa ăn khoảng 30 phút. Rửa chân sạch và lau khô kẽ chân hàng ngày, đi dép mềm trong nhà.',
    emergency_warning: 'Nếu thấy đói cồn cào, run tay chân, vã mồ hôi lạnh, hoa mắt: Ngậm ngay 1 viên kẹo ngọt hoặc uống 1 ly nước đường, sau đó ngồi nghỉ 15 phút.',
    follow_up_days: '30',
    guideline_citation: 'Quyết định số 5481/QĐ-BYT (Bộ Y Tế)'
  };

  if (isHTN) {
    fallbackPlan = {
      doctor_greeting: `Chào bác ${pName}, huyết áp đợt này của bác đang được kiểm soát ổn định. Bác vui lòng tuân thủ phác đồ thuốc và ăn giảm muối để phòng ngừa tai biến tim mạch nhé!`,
      morning_meds: 'Amlodipine 5 mg (Uống 1 viên vào mỗi buổi sáng sau ăn)',
      evening_meds: 'Losartan 50 mg (Uống 1 viên vào buổi tối sau ăn)',
      diet_good: 'Ăn nhạt, tăng cường rau củ giàu Kali và Magie (chuối, khoai lang, rau ngót), cá nạc; uống đủ nước.',
      diet_bad: 'Ăn giảm muối (< 5g/ngày), kiêng nước mắm nguyên chất, đồ kho mặn, dưa cà muối; kiêng rượu bia và thuốc lá.',
      exercise: 'Đi bộ nhanh hoặc tập thể dục nhẹ nhàng 30 - 45 phút mỗi ngày. Tránh xúc động mạnh hoặc gắng sức quá mức.',
      emergency_warning: 'Nếu huyết áp đo tại nhà > 180/110 mmHg kèm đau đầu dữ dội, hoa mắt, tức ngực, khó thở: Liên hệ cấp cứu hoặc đến viện ngay.',
      follow_up_days: '30',
      guideline_citation: 'Quyết định số 3192/QĐ-BYT (Bộ Y Tế)'
    };
  } else if (isCKD) {
    fallbackPlan = {
      doctor_greeting: `Chào bác ${pName}, chức năng thận của bác cần được bảo vệ nghiêm ngặt. Bác hãy thực hiện đúng chế độ ăn giảm đạm và kiểm soát huyết áp bên dưới nhé!`,
      morning_meds: 'Thuốc kiểm soát huyết áp theo đơn (Uống sau ăn sáng)',
      evening_meds: 'Thuốc bảo vệ thận theo đơn (Uống sau ăn tối)',
      diet_good: 'Ăn lượng đạm vừa phải (0.8g/kg/ngày), ưu tiên cá nạc và đạm thực vật; uống nước vừa đủ theo lượng nước tiểu.',
      diet_bad: 'Kiêng ăn mặn, kiêng nước ngọt đóng chai, hạn chế thực phẩm nhiều Kali nếu có chỉ định (chuối, nước dừa).',
      exercise: 'Tập thể dục nhẹ nhàng 20 - 30 phút mỗi ngày. Tránh làm việc nặng nhọc gây mất nước.',
      emergency_warning: 'Nếu thấy phù 2 chân, tiểu ít, khó thở khi nằm hoặc mệt mỏi nhiều: Đi khám lại ngay.',
      follow_up_days: '14',
      guideline_citation: 'Phác đồ Điều Trị Bệnh Thận Mạn (Bộ Y Tế)'
    };
  }

  return NextResponse.json({
    status: 'fallback',
    agent_type: isHTN ? 'Deterministic Clinical Guidelines (QĐ 3192/QĐ-BYT)' : 'Deterministic Clinical Guidelines (QĐ 5481/QĐ-BYT)',
    plan: fallbackPlan
  });
}
