import java.sql.*;
import java.io.*;
public class Q {
  public static void main(String[] a) throws Exception {
    PrintStream out = new PrintStream(new FileOutputStream(FileDescriptor.out), true, "UTF-8");
    String url = "jdbc:oracle:thin:@10.200.206.130:1521:toptest";
    StringBuilder sb = new StringBuilder();
    BufferedReader br = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
    String line; while ((line=br.readLine())!=null) sb.append(line).append("\n");
    String sql = sb.toString().trim();
    if (sql.endsWith(";")) sql = sql.substring(0, sql.length()-1);
    // 密碼不入 repo:執行前設定環境變數 ERP_DB_USER / ERP_DB_PASSWORD(見本目錄 README)
    try (Connection c = DriverManager.getConnection(url, System.getenv("ERP_DB_USER"), System.getenv("ERP_DB_PASSWORD"))) {
      Statement s = c.createStatement();
      s.setFetchSize(500);
      ResultSet r = s.executeQuery(sql);
      ResultSetMetaData m = r.getMetaData();
      int n = m.getColumnCount();
      StringBuilder h = new StringBuilder();
      for (int i=1;i<=n;i++){ if(i>1)h.append("\t"); h.append(m.getColumnName(i)); }
      out.println(h);
      int cnt=0;
      while (r.next()){
        StringBuilder rb = new StringBuilder();
        for (int i=1;i<=n;i++){ if(i>1)rb.append("\t"); String v=r.getString(i); rb.append(v==null?"":v.replace("\t"," ").replace("\r"," ").replace("\n"," ")); }
        out.println(rb); cnt++;
      }
      System.err.println("ROWS="+cnt);
    } catch (Exception e){ System.err.println("SQLERR: "+e.getMessage()); }
  }
}
